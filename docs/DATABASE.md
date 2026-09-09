# PostgreSQL / DBeaver

База `needle_shark`, PostgreSQL 16 на VPS 194.87.99.98. Порт 5432 слушает только 127.0.0.1. Подключение через SSH-туннель.

## Подключение DBeaver

Создать подключение PostgreSQL:
- Host: 127.0.0.1
- Port: 5432
- Database: needle_shark
- Username: needle_admin
- Password: из локального `server/database-access.key` (файл исключён из Git).

Вкладка SSH: включить туннель, Host 194.87.99.98, Port 22, User needledeploy, Authentication Public Key, Private key `~/.ssh/needle_shark_ed25519`. Затем Test Connection.

`needle_admin` — запрошенный владельцем SUPERUSER PostgreSQL. Учётная запись формы `needle_app` не является суперпользователем: SELECT/INSERT/UPDATE таблиц и доступ к последовательностям. Пароль приложения хранится в `/etc/needle-shark/leads.env`, права 0600. Не использовать администратора в коде сайта.

## Таблицы

`customers`: последовательный id, name, contact, уникальный нормализованный contact_key, first_inquiry_at, last_inquiry_at, created_at, notes.

`orders`: последовательный id, уникальный submission_id (UUID заявки), customer_id (FK), created_at, customer_name и contact на момент заявки, description, status (`new`), attachment_name, consent, consent_documents, notes.

Время — TIMESTAMPTZ, хранится как момент UTC; DBeaver может отображать местный часовой пояс. Номера возрастают, но могут иметь пропуски после отменённых транзакций. «Заказ» здесь означает входящую заявку, не подтверждённую покупку. Один нормализованный контакт связывает повторные обращения; это не удостоверенная личность пользователя. Имя первого обращения сохраняется в customers, имя каждого обращения — в orders.

Сначала заявка записывается в PostgreSQL, затем в SQLite-очередь доставки. При недоступной SQL-базе сервер не подтверждает приём. UUID позволяет безопасно повторить запрос. PostgreSQL хранит записи постоянно до отдельного удаления владельцем; SQLite удаляет доставленные payload через 7 дней. Файлы в PostgreSQL не хранятся, только имена; исходные вложения идут в письмо.

`server/schema.sql` — схема. `server/backfill_crm.py` переносит сохранившиеся заявки из очереди без повторных писем, повторный запуск не дублирует записи. Более старые, уже удалённые из очереди записи он восстановить не может. В базе могут быть явно помеченные технические проверки.

Резервное копирование: `pg_dump -Fc needle_shark` от postgres. Автоматический внешний бэкап пока не настроен; GitHub хранит только схему и код, не клиентские данные.
