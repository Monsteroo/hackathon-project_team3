-- Пошук товарів за назвою: нормалізований текст (нижній регістр, без лапок), який рахує ETL у Python.
-- Накопичує назви товару з різних мереж, тож «Jacobs Kronung» знайдеться за назвою і Zakaz, і Сільпо.
--
-- Навмисно без заповнення через SQL lower(): у БД з локаллю C (типово для локального Homebrew-кластера)
-- lower() не переводить кирилицю в нижній регістр, а pg_trgm не бачить у ній трійок. Колонку заповнює
-- наступний прогін ETL.

alter table products add column if not exists search_text text;

create index if not exists products_search_trgm_idx on products using gin (search_text gin_trgm_ops);
