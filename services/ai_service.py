"""
Оптимизированный сервис для работы с AI API
Включает: кэширование, retry логику, fallback, мониторинг
"""
import asyncio
import hashlib
import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from database.models import AICache
from database.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class AIService:
    """Сервис для работы с AI API с оптимизациями"""
    
    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self.timeout = aiohttp.ClientTimeout(total=settings.AI_TIMEOUT)
        
    def _hash_prompt(self, prompt: str, model: str = None) -> str:
        """Создает хэш промпта для кэширования"""
        model = model or (settings.OPENAI_MODEL if self.provider == "openai" else settings.GOOGLE_AI_MODEL)
        content = f"{prompt}:{model}:{settings.OPENAI_TEMPERATURE}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def _get_cache(self, prompt_hash: str, session: AsyncSession) -> Optional[str]:
        """Получает ответ из кэша"""
        if not settings.AI_CACHE_ENABLED:
            return None
        
        try:
            # Пробуем использовать Redis, если доступен
            redis_client = await get_redis_client()
            if redis_client:
                # Сначала проверяем Redis (быстрее)
                cache_key = f"ai_cache:{prompt_hash}"
                try:
                    cached = await redis_client.get(cache_key)
                    if cached:
                        return cached
                except Exception:
                    pass  # Игнорируем ошибки Redis
            
            # Проверяем БД
            result = await session.execute(
                select(AICache).where(
                    AICache.prompt_hash == prompt_hash,
                    AICache.expires_at > datetime.utcnow()
                )
            )
            cache_entry = result.scalar_one_or_none()
            
            if cache_entry:
                # Обновляем счетчик использования
                cache_entry.hit_count += 1
                await session.commit()
                
                # Сохраняем в Redis для следующих запросов (если доступен)
                if redis_client:
                    try:
                        cache_key = f"ai_cache:{prompt_hash}"
                        await redis_client.setex(
                            cache_key,
                            int((cache_entry.expires_at - datetime.utcnow()).total_seconds()),
                            cache_entry.response
                        )
                    except Exception:
                        pass  # Игнорируем ошибки Redis
                
                return cache_entry.response
            
        except Exception as e:
            logger.warning(f"Ошибка при получении из кэша: {e}")
        
        return None
    
    async def _save_cache(
        self, 
        prompt_hash: str, 
        response: str, 
        tokens_used: int,
        session: AsyncSession
    ):
        """Сохраняет ответ в кэш"""
        if not settings.AI_CACHE_ENABLED:
            return
        
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=settings.AI_CACHE_TTL)
            cache_key_db = f"ai_cache:{prompt_hash}"
            
            # Сохраняем в БД
            cache_entry = AICache(
                cache_key=cache_key_db,
                prompt_hash=prompt_hash,
                response=response,
                tokens_used=tokens_used,
                expires_at=expires_at
            )
            session.add(cache_entry)
            await session.commit()
            
            # Также сохраняем в Redis (если доступен)
            redis_client = await get_redis_client()
            if redis_client:
                try:
                    cache_key_redis = f"ai_cache:{prompt_hash}"
                    await redis_client.setex(
                        cache_key_redis,
                        settings.AI_CACHE_TTL,
                        response
                    )
                except Exception:
                    pass  # Игнорируем ошибки Redis
            
        except Exception as e:
            logger.warning(f"Ошибка при сохранении в кэш: {e}")
            try:
                await session.rollback()
            except:
                pass
    
    async def _call_openai(
        self, 
        prompt: str, 
        conversation_history: Optional[List[Dict[str, str]]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """Вызов OpenAI API с retry логикой"""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY не установлен")
        
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=self.timeout.total)
            
            messages = []
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": prompt})
            
            model = settings.OPENAI_MODEL
            
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=settings.OPENAI_MAX_TOKENS
            )
            
            return {
                "response": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens,
                "model": model
            }
            
        except Exception as e:
            logger.error(f"Ошибка при вызове OpenAI API: {e}")
            
            # Retry логика
            if retry_count < settings.AI_MAX_RETRIES:
                await asyncio.sleep(settings.AI_RETRY_DELAY * (retry_count + 1))
                return await self._call_openai(prompt, conversation_history, retry_count + 1)
            
            # Fallback на более дешевую модель
            if settings.AI_FALLBACK_ENABLED and model != settings.AI_FALLBACK_MODEL:
                logger.info(f"Используем fallback модель: {settings.AI_FALLBACK_MODEL}")
                try:
                    from openai import AsyncOpenAI
                    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, timeout=self.timeout.total)
                    response = await client.chat.completions.create(
                        model=settings.AI_FALLBACK_MODEL,
                        messages=messages,
                        temperature=settings.OPENAI_TEMPERATURE,
                        max_tokens=settings.OPENAI_MAX_TOKENS
                    )
                    return {
                        "response": response.choices[0].message.content,
                        "tokens_used": response.usage.total_tokens,
                        "model": settings.AI_FALLBACK_MODEL
                    }
                except Exception as fallback_error:
                    logger.error(f"Fallback также не удался: {fallback_error}")
            
            raise
    
    async def _call_google_ai(
        self, 
        prompt: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """Вызов Google AI API с retry логикой"""
        if not settings.GOOGLE_AI_API_KEY:
            raise ValueError("GOOGLE_AI_API_KEY не установлен")
        
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=settings.GOOGLE_AI_API_KEY)
            
            # Используем правильное имя модели
            # Для новых моделей нужно использовать полный путь или упрощенное имя
            model_name = settings.GOOGLE_AI_MODEL
            
            # Если модель указана как gemini-1.5-flash, пробуем разные варианты
            if model_name == "gemini-1.5-flash":
                # Пробуем сначала упрощенное имя
                try:
                    model = genai.GenerativeModel("gemini-1.5-flash")
                except:
                    # Если не работает, пробуем полный путь
                    try:
                        model = genai.GenerativeModel("models/gemini-1.5-flash")
                    except:
                        # Fallback на старую модель
                        model = genai.GenerativeModel("gemini-pro")
                        model_name = "gemini-pro"
            elif model_name == "gemini-1.5-pro":
                try:
                    model = genai.GenerativeModel("gemini-1.5-pro")
                except:
                    model = genai.GenerativeModel("gemini-pro")
                    model_name = "gemini-pro"
            else:
                model = genai.GenerativeModel(model_name)
            
            # Формируем полный промпт с историей (простой способ для старого API)
            full_prompt = prompt
            if conversation_history:
                context_parts = []
                for msg in conversation_history:
                    role_name = "Пользователь" if msg['role'] == "user" else "Ассистент"
                    context_parts.append(f"{role_name}: {msg['content']}")
                context = "\n".join(context_parts)
                full_prompt = f"{context}\n\nПользователь: {prompt}\nАссистент:"
            
            # Генерируем ответ (передаем текст напрямую)
            response = await asyncio.to_thread(
                model.generate_content,
                full_prompt,
                generation_config={
                    "temperature": settings.GOOGLE_AI_TEMPERATURE,
                    "max_output_tokens": settings.OPENAI_MAX_TOKENS,
                }
            )
            
            # Получаем текст ответа
            response_text = response.text if hasattr(response, 'text') else str(response)
            
            # Подсчет токенов (приблизительно)
            prompt_tokens = len(full_prompt.split())
            response_tokens = len(response_text.split())
            tokens_used = prompt_tokens + response_tokens
            
            return {
                "response": response_text,
                "tokens_used": tokens_used,
                "model": model_name
            }
            
        except Exception as e:
            logger.error(f"Ошибка при вызове Google AI API: {e}")
            
            if retry_count < settings.AI_MAX_RETRIES:
                await asyncio.sleep(settings.AI_RETRY_DELAY * (retry_count + 1))
                return await self._call_google_ai(prompt, conversation_history, retry_count + 1)
            
            raise
    
    async def process_text(
        self,
        prompt: str,
        user_id: int,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает текстовый запрос пользователя
        
        Returns:
            Dict с ключами: response, tokens_used, model, from_cache, processing_time
        """
        start_time = time.time()
        
        # Проверяем кэш
        prompt_hash = self._hash_prompt(prompt)
        cached_response = None
        
        if session:
            cached_response = await self._get_cache(prompt_hash, session)
        
        if cached_response:
            processing_time = int((time.time() - start_time) * 1000)
            return {
                "response": cached_response,
                "tokens_used": 0,
                "model": f"{self.provider}_cached",
                "from_cache": True,
                "processing_time": processing_time
            }
        
        # Вызываем AI API
        try:
            if self.provider == "openai":
                result = await self._call_openai(prompt, conversation_history)
            elif self.provider == "google":
                result = await self._call_google_ai(prompt, conversation_history)
            else:
                raise ValueError(f"Неподдерживаемый провайдер: {self.provider}")
            
            processing_time = int((time.time() - start_time) * 1000)
            result["from_cache"] = False
            result["processing_time"] = processing_time
            
            # Сохраняем в кэш
            if session:
                await self._save_cache(prompt_hash, result["response"], result["tokens_used"], session)
            
            return result
            
        except Exception as e:
            logger.error(f"Критическая ошибка при обработке AI запроса: {e}")
            raise
    
    def estimate_cost(self, tokens_used: int, model: str) -> int:
        """
        Оценивает стоимость запроса в центах
        Примерные цены (нужно обновить актуальными)
        """
        # Цены в долларах за 1M токенов
        pricing = {
            "gpt-4-turbo-preview": {"input": 10, "output": 30},  # $10/$30 за 1M
            "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},  # $0.5/$1.5 за 1M
            "gemini-pro": {"input": 0.25, "output": 0.5},  # Примерные цены
        }
        
        if model not in pricing:
            return 0
        
        # Приблизительная оценка (предполагаем 50/50 input/output)
        avg_price = (pricing[model]["input"] + pricing[model]["output"]) / 2
        cost_dollars = (tokens_used / 1_000_000) * avg_price
        return int(cost_dollars * 100)  # В центах


# Singleton экземпляр
ai_service = AIService()

