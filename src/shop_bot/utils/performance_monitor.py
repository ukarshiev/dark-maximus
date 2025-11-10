# -*- coding: utf-8 -*-
"""
Модуль для мониторинга производительности бота
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict, deque
import json
from functools import wraps

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """Метрика производительности"""
    timestamp: float
    operation: str
    duration: float
    user_id: Optional[int] = None
    success: bool = True
    error: Optional[str] = None

class PerformanceMonitor:
    """Монитор производительности бота"""
    
    def __init__(self, max_metrics: int = 1000, slow_threshold: float = 1.0, enabled: bool = True):
        # Глобальные настройки монитора
        self.max_metrics = max_metrics
        self.slow_threshold = slow_threshold
        self.enabled = enabled
        # Хранилище метрик (ограниченное deque)
        self.metrics: deque = deque(maxlen=max_metrics)
        self.operation_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'avg_time': 0.0,
            'min_time': float('inf'),
            'max_time': 0.0,
            'slow_count': 0,
            'error_count': 0
        })
        self.user_stats: Dict[int, Dict[str, Any]] = defaultdict(lambda: {
            'request_count': 0,
            'total_time': 0.0,
            'avg_time': 0.0,
            'slow_requests': 0
        })
        self._lock = asyncio.Lock()
    
    async def apply_settings(self, *, max_metrics: Optional[int] = None, slow_threshold: Optional[float] = None, enabled: Optional[bool] = None):
        """Применение новых настроек для монитора на лету.
        Безопасно пересоздает deque при изменении лимита и обновляет порог/флаг включения.
        """
        async with self._lock:
            if max_metrics is not None and max_metrics != self.max_metrics and max_metrics > 0:
                # Пересоздаем deque с новым maxlen, сохранив последние элементы
                new_deque: deque = deque(self.metrics, maxlen=max_metrics)
                self.metrics = new_deque
                self.max_metrics = max_metrics
            if slow_threshold is not None and slow_threshold > 0:
                self.slow_threshold = slow_threshold
            if enabled is not None:
                self.enabled = bool(enabled)
    
    async def set_enabled(self, value: bool):
        async with self._lock:
            self.enabled = bool(value)
    
    async def record_metric(
        self, 
        operation: str, 
        duration: float, 
        user_id: Optional[int] = None,
        success: bool = True,
        error: Optional[str] = None
    ):
        """Запись метрики производительности"""
        async with self._lock:
            if not self.enabled:
                return
            metric = PerformanceMetric(
                timestamp=time.time(),
                operation=operation,
                duration=duration,
                user_id=user_id,
                success=success,
                error=error
            )
            
            self.metrics.append(metric)
            
            # Обновляем статистику операций
            op_stats = self.operation_stats[operation]
            op_stats['count'] += 1
            op_stats['total_time'] += duration
            op_stats['avg_time'] = op_stats['total_time'] / op_stats['count']
            op_stats['min_time'] = min(op_stats['min_time'], duration)
            op_stats['max_time'] = max(op_stats['max_time'], duration)
            
            if duration > self.slow_threshold:
                op_stats['slow_count'] += 1
            
            if not success:
                op_stats['error_count'] += 1
            
            # Обновляем статистику пользователей
            if user_id:
                user_stats = self.user_stats[user_id]
                user_stats['request_count'] += 1
                user_stats['total_time'] += duration
                user_stats['avg_time'] = user_stats['total_time'] / user_stats['request_count']
                
                if duration > self.slow_threshold:
                    user_stats['slow_requests'] += 1
    
    async def get_operation_stats(self, operation: str) -> Dict[str, Any]:
        """Получение статистики по операции"""
        async with self._lock:
            return self.operation_stats.get(operation, {}).copy()
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получение статистики по пользователю"""
        async with self._lock:
            return self.user_stats.get(user_id, {}).copy()
    
    async def get_slow_operations(self, limit: int = 10) -> List[PerformanceMetric]:
        """Получение медленных операций"""
        async with self._lock:
            slow_ops = [m for m in self.metrics if m.duration > self.slow_threshold]
            return sorted(slow_ops, key=lambda x: x.duration, reverse=True)[:limit]
    
    async def get_recent_errors(self, limit: int = 10) -> List[PerformanceMetric]:
        """Получение последних ошибок"""
        async with self._lock:
            errors = [m for m in self.metrics if not m.success]
            return sorted(errors, key=lambda x: x.timestamp, reverse=True)[:limit]
    
    async def get_performance_summary(self) -> Dict[str, Any]:
        """Получение сводки по производительности"""
        async with self._lock:
            if not self.metrics:
                return {
                    'total_operations': 0,
                    'avg_response_time': 0.0,
                    'slow_operations': 0,
                    'error_rate': 0.0,
                    'top_operations': [],
                    'top_users': []
                }
            
            total_ops = len(self.metrics)
            total_time = sum(m.duration for m in self.metrics)
            avg_time = total_time / total_ops if total_ops > 0 else 0.0
            slow_ops = sum(1 for m in self.metrics if m.duration > self.slow_threshold)
            error_ops = sum(1 for m in self.metrics if not m.success)
            error_rate = (error_ops / total_ops) * 100 if total_ops > 0 else 0.0
            
            # Топ операций по времени выполнения
            op_times = defaultdict(list)
            for metric in self.metrics:
                op_times[metric.operation].append(metric.duration)
            
            top_operations = []
            for op, times in op_times.items():
                avg_op_time = sum(times) / len(times)
                top_operations.append({
                    'operation': op,
                    'count': len(times),
                    'avg_time': avg_op_time,
                    'total_time': sum(times)
                })
            
            top_operations.sort(key=lambda x: x['total_time'], reverse=True)
            
            # Топ пользователей по количеству запросов
            user_counts = defaultdict(int)
            for metric in self.metrics:
                if metric.user_id:
                    user_counts[metric.user_id] += 1
            
            # Получаем дополнительную информацию о пользователях
            top_users = []
            for user_id, count in sorted(user_counts.items(), key=lambda x: x[1], reverse=True):
                user_info = {'user_id': user_id, 'request_count': count, 'username': 'N/A', 'fullname': 'N/A'}
                
                # Получаем данные пользователя из базы данных
                try:
                    from shop_bot.data_manager.database import get_user
                    user_data = get_user(user_id)
                    if user_data:
                        user_info['username'] = user_data.get('username') or 'N/A'
                        user_info['fullname'] = user_data.get('fullname') or 'N/A'
                except Exception as e:
                    logger.warning(f"Failed to get user data for {user_id}: {e}")
                
                top_users.append(user_info)
            
            return {
                'total_operations': total_ops,
                'avg_response_time': avg_time,
                'slow_operations': slow_ops,
                'error_rate': error_rate,
                'top_operations': top_operations[:20],
                'top_users': top_users[:20]
            }
    
    async def clear_old_metrics(self, max_age_hours: int = 24):
        """Очистка старых метрик"""
        async with self._lock:
            cutoff_time = time.time() - (max_age_hours * 3600)
            old_count = len(self.metrics)
            
            # Удаляем старые метрики
            while self.metrics and self.metrics[0].timestamp < cutoff_time:
                self.metrics.popleft()
            
            removed_count = old_count - len(self.metrics)
            if removed_count > 0:
                logger.info(f"Cleared {removed_count} old metrics")
    
    async def export_metrics(self, file_path: str):
        """Экспорт метрик в файл"""
        async with self._lock:
            metrics_data = []
            for metric in self.metrics:
                metrics_data.append({
                    'timestamp': metric.timestamp,
                    'operation': metric.operation,
                    'duration': metric.duration,
                    'user_id': metric.user_id,
                    'success': metric.success,
                    'error': metric.error
                })
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(metrics_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Exported {len(metrics_data)} metrics to {file_path}")
    
    async def export_metrics_json(self) -> list:
        """Экспорт метрик в виде JSON-совместимого списка (для HTTP ответа)."""
        async with self._lock:
            return [
                {
                    'timestamp': metric.timestamp,
                    'operation': metric.operation,
                    'duration': metric.duration,
                    'user_id': metric.user_id,
                    'success': metric.success,
                    'error': metric.error
                }
                for metric in self.metrics
            ]
    
    async def get_hourly_stats_for_charts(self, hours: int = 24) -> dict:
        """Получение статистики по часам за последние N часов для графиков"""
        async with self._lock:
            if not self.metrics:
                return {
                    'hours': [],
                    'total_operations': [],
                    'avg_response_time': [],
                    'slow_operations': [],
                    'error_count': []
                }
            
            from datetime import datetime, timedelta
            import time
            
            # Создаем список всех часов за последние N часов
            current_time = time.time()
            hours_list = []
            for i in range(hours):
                hour_time = current_time - (i * 3600)
                hour_datetime = datetime.fromtimestamp(hour_time)
                hours_list.append(hour_datetime.strftime('%H:00'))
            
            hours_list.reverse()  # От старых к новым
            
            # Инициализируем словари для группировки по часам
            hourly_stats = {}
            for i in range(hours):
                hour_time = current_time - (i * 3600)
                hour_key = int(hour_time // 3600) * 3600  # Округляем до часа
                hourly_stats[hour_key] = {
                    'total_operations': 0,
                    'total_duration': 0.0,
                    'slow_operations': 0,
                    'error_count': 0
                }
            
            # Группируем метрики по часам
            for metric in self.metrics:
                hour_key = int(metric.timestamp // 3600) * 3600
                if hour_key in hourly_stats:
                    hourly_stats[hour_key]['total_operations'] += 1
                    hourly_stats[hour_key]['total_duration'] += metric.duration
                    
                    if metric.duration > self.slow_threshold:
                        hourly_stats[hour_key]['slow_operations'] += 1
                    
                    if not metric.success:
                        hourly_stats[hour_key]['error_count'] += 1
            
            # Создаем массивы данных для графиков
            total_operations = []
            avg_response_time = []
            slow_operations = []
            error_count = []
            
            for i in range(hours):
                hour_time = current_time - (i * 3600)
                hour_key = int(hour_time // 3600) * 3600
                
                stats = hourly_stats.get(hour_key, {
                    'total_operations': 0,
                    'total_duration': 0.0,
                    'slow_operations': 0,
                    'error_count': 0
                })
                
                total_operations.append(stats['total_operations'])
                
                # Среднее время ответа
                if stats['total_operations'] > 0:
                    avg_time = stats['total_duration'] / stats['total_operations']
                else:
                    avg_time = 0.0
                avg_response_time.append(round(avg_time, 3))
                
                slow_operations.append(stats['slow_operations'])
                error_count.append(stats['error_count'])
            
            return {
                'hours': hours_list,
                'total_operations': total_operations,
                'avg_response_time': avg_response_time,
                'slow_operations': slow_operations,
                'error_count': error_count
            }

# Глобальный экземпляр монитора
_performance_monitor: Optional[PerformanceMonitor] = None

def get_performance_monitor() -> PerformanceMonitor:
    """Получение глобального экземпляра монитора производительности"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor

# Декоратор для измерения производительности
def measure_performance(operation_name: str):
    """Декоратор для измерения производительности функции"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            error = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                duration = time.time() - start_time
                user_id = None
                
                # Пытаемся извлечь user_id из аргументов
                for arg in args:
                    if hasattr(arg, 'from_user') and hasattr(arg.from_user, 'id'):
                        user_id = arg.from_user.id
                        break
                
                monitor = get_performance_monitor()
                await monitor.record_metric(
                    operation=operation_name,
                    duration=duration,
                    user_id=user_id,
                    success=success,
                    error=error
                )
        
        return wrapper
    return decorator

# Функция для периодической очистки старых метрик
async def start_metrics_cleanup():
    """Запуск периодической очистки метрик.
    Интервал/порог читаются из настроек БД, если доступны.
    """
    monitor = get_performance_monitor()
    # Поздний импорт, чтобы избежать циклических зависимостей при запуске
    try:
        from shop_bot.data_manager import database  # type: ignore
    except Exception:
        database = None  # fallback
    
    while True:
        try:
            # Периодичность проверки (по умолчанию 1 час)
            sleep_seconds = 3600
            max_age_hours = 24
            if database:
                try:
                    # Настройка хранения метрик (в часах): допустимые значения 0.5,1,2,6,12,24
                    raw_hours = database.get_setting('monitoring_cleanup_hours')
                    if raw_hours:
                        max_age_hours = float(raw_hours)
                    # Частоту сна оставляем час, чтобы не создавать лишнюю нагрузку
                except Exception:
                    pass
            await asyncio.sleep(sleep_seconds)
            await monitor.clear_old_metrics(max_age_hours=int(max_age_hours) if max_age_hours >= 1 else 1)
        except Exception as e:
            logger.error(f"Error in metrics cleanup: {e}")

# Функция для получения отчета о производительности
async def get_performance_report() -> str:
    """Получение отчета о производительности в текстовом формате"""
    monitor = get_performance_monitor()
    summary = await monitor.get_performance_summary()
    
    report = f"""
📊 **Отчет о производительности бота**

**Общая статистика:**
• Всего операций: {summary['total_operations']}
• Среднее время ответа: {summary['avg_response_time']:.3f}с
• Медленных операций: {summary['slow_operations']}
• Процент ошибок: {summary['error_rate']:.1f}%

**Топ операций по времени выполнения:**
"""
    
    for i, op in enumerate(summary['top_operations'], 1):
        report += f"{i}. {op['operation']}: {op['count']} раз, {op['avg_time']:.3f}с среднее\n"
    
    report += "\n**Топ пользователей по активности:**\n"
    for i, user in enumerate(summary['top_users'], 1):
        report += f"{i}. Пользователь {user['user_id']}: {user['request_count']} запросов\n"
    
    return report
