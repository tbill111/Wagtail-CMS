-- Patch dữ liệu đi kèm migration crm.0004_product_stock (SQLite)
-- Mục đích: CSDL đã có đơn hàng từ trước (OrderItem chỉ có product_name gõ tay)
--   1. Tạo Product cho mỗi tên sản phẩm chưa có trong danh mục (SKU dạng OLD-0001)
--   2. Gắn OrderItem.product vào Product vừa tạo theo đúng tên
-- Product tạo ra để track_stock = 0 (chưa biết tồn kho thật) nên không trừ kho đơn cũ.
-- Bật "Quản lý tồn kho" và nhập tồn kho cho từng sản phẩm trong Wagtail Admin sau khi patch.
--
-- Chạy:  sqlite3 db.sqlite3 < docs/patches/0004_backfill_products.sql
-- Không cần chạy với CSDL demo: dùng `python manage.py seed_demo --reset` là đủ.

-- ---------------------------------------------------------------- VERIFY (trước)
SELECT 'truoc: dong chua gan san pham' AS kiem_tra, COUNT(*) AS so_luong
FROM crm_orderitem WHERE product_id IS NULL;

BEGIN TRANSACTION;

INSERT INTO crm_product (sku, name, unit, price, track_stock, stock, min_stock, is_active, created_at)
SELECT
    'OLD-' || printf('%04d', ROW_NUMBER() OVER (ORDER BY TRIM(oi.product_name))),
    TRIM(oi.product_name),
    'cái',
    MAX(oi.unit_price),
    0, 0, 0, 1,
    strftime('%Y-%m-%d %H:%M:%f', 'now')
FROM crm_orderitem oi
WHERE oi.product_id IS NULL
  AND TRIM(oi.product_name) <> ''
  AND TRIM(oi.product_name) NOT IN (SELECT name FROM crm_product)
GROUP BY TRIM(oi.product_name);

UPDATE crm_orderitem
SET product_id = (
    SELECT p.id FROM crm_product p WHERE p.name = TRIM(crm_orderitem.product_name) ORDER BY p.id LIMIT 1
)
WHERE product_id IS NULL AND TRIM(product_name) <> '';

COMMIT;

-- ---------------------------------------------------------------- VERIFY (sau)
-- Kỳ vọng: 0 dòng chưa gắn sản phẩm (trừ dòng có tên rỗng)
SELECT 'sau: dong chua gan san pham' AS kiem_tra, COUNT(*) AS so_luong
FROM crm_orderitem WHERE product_id IS NULL;

-- Danh sách sản phẩm được tạo và số dòng đơn đã gắn
SELECT p.sku, p.name, p.price, COUNT(oi.id) AS so_dong_don
FROM crm_product p LEFT JOIN crm_orderitem oi ON oi.product_id = p.id
WHERE p.sku LIKE 'OLD-%'
GROUP BY p.id ORDER BY p.sku;
