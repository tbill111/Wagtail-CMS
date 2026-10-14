# Kịch bản quay video demo SmartCRM

Thời lượng dự kiến: **9–11 phút**, gồm 8 cảnh. Mỗi cảnh có: link, thao tác, lời thoại gợi ý, và những gì phải thấy trên màn hình.
Lời thoại chỉ là gợi ý: đọc tự nhiên, không cần thuộc nguyên văn.

---

## 0. Chuẩn bị trước khi quay (làm 1 lần, không quay)

### 0.1. Khởi động hệ thống
Mở PowerShell tại thư mục `smartcrm` (thư mục chứa `manage.py`):

```powershell
..\venv\Scripts\Activate.ps1                   # venv nằm ở thư mục cha
python manage.py migrate                       # áp dụng đủ migration 0001–0004
python manage.py seed_demo --reset --analyze   # dữ liệu mẫu sạch: 10 khách, 17 đơn, 13 sản phẩm
python manage.py runserver
```

Thấy dòng `Starting development server at http://127.0.0.1:8000/` là xong. **Không tắt cửa sổ này trong lúc quay.**

> Chạy lại `seed_demo --reset --analyze` **trước mỗi lần quay lại** để dữ liệu (tồn kho, đơn hàng) về đúng trạng thái ban đầu.

### 0.2. Chọn chế độ AI
- **Nên dùng AI Gemini thật** (video thuyết phục hơn): trong `.env` có `GEMINI_API_KEY=<key>` và `AI_MOCK=False`.
- Mạng yếu hoặc hết quota thì đặt `AI_MOCK=True`, rồi khởi động lại `runserver`. Khi đó giao diện hiện nhãn "(chế độ mô phỏng)"; nói rõ điều này trong video.
- Trước khi quay, bấm thử **✨ Gợi ý phản hồi** 1 lần để chắc chắn AI trả lời được.

### 0.3. Chuẩn bị trình duyệt
- Dùng Chrome/Edge, **đăng nhập sẵn** bằng tài khoản superuser (tạo bằng `python manage.py createsuperuser` nếu chưa có).
- Zoom **110–125%** (Ctrl + dấu cộng) để chữ đọc được trên video. Ẩn thanh bookmark (Ctrl+Shift+B).
- Mở sẵn 3 tab theo thứ tự:
  1. <http://127.0.0.1:8000/crm/> (Tổng quan)
  2. <http://127.0.0.1:8000/admin/> (Wagtail Admin)
  3. <http://127.0.0.1:8000/crm/reports/> (Báo cáo AI)
- Tắt thông báo Windows/Zalo/Messenger (Focus Assist).

### 0.4. Phần mềm quay
- **OBS Studio** (miễn phí) hoặc **Xbox Game Bar** (Win + Alt + R) có sẵn trên Windows 11.
- Quay 1080p, bật micro. Có thể quay từng cảnh riêng rồi ghép lại.

---

## 1. Danh sách link dùng trong video

| # | Link | Trang |
|---|---|---|
| 1 | <http://127.0.0.1:8000/> | Trang chủ giới thiệu |
| 2 | <http://127.0.0.1:8000/admin/> | Wagtail Admin (nhập liệu) |
| 3 | <http://127.0.0.1:8000/admin/snippets/crm/product/> | Admin → Sản phẩm & tồn kho |
| 4 | <http://127.0.0.1:8000/admin/snippets/crm/order/> | Admin → Đơn hàng |
| 5 | <http://127.0.0.1:8000/crm/> | SmartCRM – Tổng quan (biểu đồ, cảnh báo kho) |
| 6 | <http://127.0.0.1:8000/crm/customers/> | Danh sách khách hàng |
| 7 | `http://127.0.0.1:8000/crm/customers/<id>/` | Chi tiết khách + 2 khối AI (mở từ danh sách, bấm **Chi tiết**) |
| 8 | <http://127.0.0.1:8000/crm/reports/> | Báo cáo AI |
| 9 | <http://127.0.0.1:8000/admin/snippets/crm/interactionlog/> | Admin → Lịch sử tương tác |
| 10 | <http://127.0.0.1:8000/admin/snippets/crm/aireport/> | Admin → Báo cáo AI đã lưu |

---

## 2. Kịch bản chi tiết

### Cảnh 1: Giới thiệu (≈ 45 giây)
**Link:** <http://127.0.0.1:8000/>

**Thao tác:** Để màn hình ở trang chủ, cuộn nhẹ xuống.

**Lời thoại:**
> Xin chào thầy/cô và các bạn. Nhóm 3 xin giới thiệu **SmartCRM**, hệ thống quản lý quan hệ khách hàng tích hợp trợ lý AI Gemini, xây dựng trên nền tảng **Wagtail CMS** với Python và Django.
> Hệ thống giải quyết bài toán: nhân viên bán hàng cần nắm thông tin khách, trả lời khách nhanh, biết khách nào cần ưu tiên và nắm tình hình kinh doanh.
> Luồng dữ liệu chính là: **nhập liệu ở Admin → AI xử lý → hiển thị ở giao diện → lưu ngược vào cơ sở dữ liệu**.

**Chuyển cảnh:** Bấm **Vào hệ thống**.

---

### Cảnh 2: Trang Tổng quan và biểu đồ (≈ 1 phút 30 giây)
**Link:** <http://127.0.0.1:8000/crm/>

**Thao tác và phải thấy:**
1. Chỉ vào **4 thẻ số liệu**: Tổng khách hàng, Khách mới trong tháng, Doanh thu đơn hoàn thành, Tương tác 7 ngày qua.
2. Rê chuột lên cột của biểu đồ **Doanh thu theo tháng**: tooltip hiện số tiền dạng "19.600.000 ₫".
3. Lần lượt chỉ vào **Khách hàng theo trạng thái**, **Top 5 khách chi tiêu nhiều**, **Top 5 sản phẩm bán chạy** (đứng đầu là *Giấy in K80*, 12 thùng).
4. Bấm **Xem bảng số liệu** dưới một biểu đồ để mở bảng số.
5. Cuộn xuống khối **⚠️ Sản phẩm sắp hết hàng**: có 3 sản phẩm (Giấy in K80 còn 2, Két đựng tiền còn 2, Máy in hoá đơn nhiệt còn 2), nhãn **! Cần nhập thêm**.
6. Cuộn tiếp tới **✨ Khách hàng ưu tiên cao (theo AI)** và **5 tương tác mới nhất**.

**Lời thoại:**
> Đây là trang Tổng quan. Phía trên là các chỉ số chính. Bên dưới là 4 biểu đồ lấy trực tiếp từ cơ sở dữ liệu: doanh thu theo tháng, phân bố khách theo trạng thái, top khách chi tiêu nhiều và top sản phẩm bán chạy.
> Hệ thống còn tự cảnh báo những sản phẩm có tồn kho dưới mức tối thiểu, như Giấy in K80 chỉ còn 2 thùng.
> Khối màu tím là danh sách khách mà AI đánh giá cần ưu tiên cao.

---

### Cảnh 3: Quản lý dữ liệu trong Wagtail Admin (≈ 2 phút)
**Link:** <http://127.0.0.1:8000/admin/> (có thể bấm **Vào Admin** trên thanh điều hướng)

**3a. Sản phẩm & tồn kho**
1. Menu trái: **CRM → Sản phẩm & tồn kho**. Chỉ vào các cột SKU, Giá bán, Tồn kho, Tồn kho tối thiểu, **Sắp hết hàng**.
2. Ghi nhớ tồn kho của **TB-POS – Máy bán hàng POS cảm ứng** (4) và **TB-KET – Két đựng tiền** (2).

> Sản phẩm được quản lý theo mã SKU, có giá bán, tồn kho và mức tồn tối thiểu. Dịch vụ như gói phần mềm thì không cần quản lý kho.

**3b. Hoàn thành đơn: kho tự trừ**
1. **CRM → Đơn hàng**, mở đơn của **Đặng Quốc Huy** (trạng thái *Đang xử lý*, gồm Máy POS và Két đựng tiền).
2. Đổi *Trạng thái* thành **Hoàn thành**, bấm **Lưu**.
3. Quay lại **Sản phẩm & tồn kho**: POS còn **3**, Két đựng tiền còn **1**.

> Khi đơn chuyển sang Hoàn thành, hệ thống tự trừ kho. Nếu huỷ hoặc sửa đơn, kho được hoàn lại đúng phần chênh lệch.

**3c. Chặn xuất vượt tồn kho**
1. **CRM → Đơn hàng → Thêm Đơn hàng**.
2. *Khách hàng*: bấm **Chọn Khách hàng** (Admin để tiếng Anh thì nút ghi *Choose Khách hàng*), chọn **Trần Thị Bình**. *Trạng thái* = **Hoàn thành**.
3. Dòng sản phẩm: bấm **Chọn Sản phẩm**, chọn **TB-K80 – Giấy in K80 (thùng)**, *Số lượng* = **5**. Để trống *Tên hiển thị* và *Đơn giá*.
4. Bấm **Lưu**. Phải thấy lỗi: *"Không đủ hàng trong kho: Giấy in K80 (thùng) (TB-K80): cần xuất 5, tồn kho chỉ còn 2"*. Đơn không được lưu.
5. Sửa *Số lượng* thành **2**, bấm **Lưu**. Đơn được tạo với **mã tự sinh** `DH-YYYYMMDD-xxxx`. Tên và đơn giá tự lấy theo sản phẩm.

> Hệ thống không cho hoàn thành đơn khi kho không đủ hàng. Mã đơn được tự sinh, tên và đơn giá tự điền theo sản phẩm đã chọn.

---

### Cảnh 4: AI gợi ý email phản hồi khách (≈ 2 phút)
**Link:** <http://127.0.0.1:8000/crm/customers/>

1. Gõ **Cường** vào ô tìm kiếm, bấm **Lọc**, bấm **Chi tiết** ở dòng *Lê Hoàng Cường*.
2. Giới thiệu nhanh cột trái: thông tin khách, đơn hàng *Thiết kế website* đang chờ duyệt, tổng chi tiêu.
3. Ở khối **✨ Gợi ý phản hồi AI**, dán tin nhắn:
   > Mình đã xem báo giá thiết kế website 9,5 triệu, hơi cao so với ngân sách. Bên bạn có giảm giá hoặc gói nhỏ hơn không?
4. Chọn *Giọng văn* = **Thân thiện**, *Kênh* = **Email**. Bấm **✨ Gợi ý phản hồi**.
5. Chờ: nút hiện "✨ AI đang soạn…". Email gợi ý hiện ra, **có tên khách và nhắc đúng đơn thiết kế website**. Trang **không tải lại**.
6. Sửa thêm 1 câu, ví dụ *"Em sẽ gọi lại cho anh chiều nay ạ."*
7. Bấm **💾 Lưu vào lịch sử**. Tương tác mới hiện đầu mục *Lịch sử tương tác*, có nhãn **✨ AI hỗ trợ**.

**Lời thoại:**
> Khi khách gửi tin nhắn, nhân viên chỉ cần dán vào đây và chọn giọng văn. AI đọc dữ liệu thật của khách (trạng thái, đơn hàng, lịch sử trao đổi) để soạn email phù hợp. Như các bạn thấy, AI nhắc đúng tên anh Cường và đơn thiết kế website.
> Nhân viên có thể chỉnh sửa trước khi gửi. Bấm Lưu thì nội dung được ghi vào lịch sử tương tác, lưu cả bản AI gợi ý lẫn bản cuối cùng đã sửa.

---

### Cảnh 5: AI phân loại khách hàng (≈ 1 phút 15 giây)
**Link:** vẫn ở trang chi tiết *Lê Hoàng Cường*

1. Ở khối **✨ Phân loại AI**, bấm **✨ Phân tích lại** (dữ liệu mẫu đã phân tích sẵn nên nút có chữ "lại").
2. Phải thấy: badge **cảm xúc** (Tích cực/Trung lập/Tiêu cực), badge **ưu tiên** (Cao/Trung bình/Thấp), đoạn tóm tắt và danh sách **hành động tiếp theo**.
3. Nếu AI đề xuất trạng thái khác trạng thái hiện tại, bấm **Áp dụng**: badge trạng thái ở đầu trang đổi ngay.

**Lời thoại:**
> Tính năng thứ hai: AI phân tích toàn bộ tương tác để đánh giá cảm xúc của khách, mức độ ưu tiên, đề xuất trạng thái mới và gợi ý hành động tiếp theo. Chỉ cần một cú bấm là áp dụng được trạng thái AI đề xuất.

---

### Cảnh 6: Báo cáo nhận định nhanh bằng AI (≈ 1 phút 15 giây)
**Link:** <http://127.0.0.1:8000/crm/reports/> (hoặc bấm **Báo cáo AI** trên thanh điều hướng)

1. Chỉ vào các thẻ số liệu phía trên.
2. Bấm **✨ Tạo báo cáo nhận định**. Chờ AI viết xong.
3. Đọc lướt 3 phần: **TÌNH HÌNH CHUNG**, **RỦI RO CẦN CHÚ Ý**, **ĐỀ XUẤT HÀNH ĐỘNG**. Chỉ vào dòng AI nhắc **sản phẩm sắp hết hàng** và đề xuất nhập thêm.
4. Bấm **Sao chép báo cáo**. Báo cáo mới xuất hiện ở mục **5 báo cáo gần nhất**.

**Lời thoại:**
> Tính năng thứ ba: AI tổng hợp số liệu từ cơ sở dữ liệu (khách hàng, doanh thu, đơn hàng, sản phẩm bán chạy, tồn kho) và viết nhận định kinh doanh gồm 3 phần. AI chỉ dựa trên số liệu thật, không bịa. Ví dụ ở đây AI đã phát hiện các sản phẩm sắp hết và đề xuất nhập thêm hàng.

---

### Cảnh 7: Dữ liệu AI được lưu ngược vào Admin (≈ 1 phút)
**Link:** <http://127.0.0.1:8000/admin/>

1. **CRM → Lịch sử tương tác**, mở bản ghi mới nhất (của Lê Hoàng Cường). Chỉ vào: *Gợi ý phản hồi của AI* (bản gốc), *Phản hồi đã gửi* (bản đã sửa), ô *Có dùng AI* được tích, *Nhân viên xử lý*.
2. **CRM → Khách hàng**, mở *Lê Hoàng Cường*, cuộn tới panel **Phân tích AI** (chỉ xem, không sửa được).
3. **CRM → Báo cáo AI**, mở báo cáo vừa tạo: có nội dung, số liệu JSON và người tạo.
4. Quay lại <http://127.0.0.1:8000/crm/>: thẻ **Tương tác 7 ngày qua** đã tăng; biểu đồ doanh thu tháng này tăng thêm nhờ 2 đơn vừa hoàn thành; khối sắp hết hàng giờ có thêm **TB-KET còn 1**.

**Lời thoại:**
> Mọi kết quả AI đều được lưu lại trong cơ sở dữ liệu và xem được trong trang quản trị. Đây chính là luồng khép kín: Admin nhập liệu, AI xử lý, giao diện hiển thị, và kết quả quay về Admin.

---

### Cảnh 8: Kết thúc (≈ 30 giây)
**Thao tác:** (tuỳ chọn) Bấm F12 → Ctrl+Shift+M → chọn iPhone để cho thấy giao diện hiển thị tốt trên điện thoại. Sau đó đóng lại, để màn hình ở trang Tổng quan.

**Lời thoại:**
> Tóm lại, SmartCRM gồm: quản lý khách hàng, đơn hàng, sản phẩm và tồn kho trên Wagtail CMS; dashboard với biểu đồ trực quan; và 3 tính năng AI: gợi ý email, phân loại khách hàng, báo cáo nhận định. Hệ thống có 81 bài kiểm thử tự động và có thể triển khai bằng Docker.
> Cảm ơn thầy/cô và các bạn đã theo dõi.

---

## 3. Xử lý sự cố khi quay

| Sự cố | Cách xử lý |
|---|---|
| AI báo lỗi / quá tải (503) | Đợi vài giây rồi bấm lại. Vẫn lỗi thì đặt `AI_MOCK=True` trong `.env`, khởi động lại `runserver`, quay lại cảnh đó |
| Mở `/crm/` bị chuyển sang trang đăng nhập | Đăng nhập lại bằng tài khoản superuser |
| Số tồn kho / đơn hàng khác kịch bản | Tắt server, chạy `python manage.py seed_demo --reset --analyze`, chạy lại `runserver` |
| Biểu đồ không hiện | Cần Internet để tải Chart.js và Bootstrap từ CDN; kiểm tra mạng rồi tải lại trang (F5) |
| Không lưu được đơn ở cảnh 3c dù số lượng = 2 | Kiểm tra đã chạy lại seed trước khi quay (tồn kho Giấy in K80 phải là 2) |
| Cổng 8000 bị chiếm | `python manage.py runserver 8080`, thay `8000` bằng `8080` trong các link |

## 4. Checklist trước khi bấm quay
- [ ] Đã chạy `seed_demo --reset --analyze`
- [ ] `runserver` đang chạy, đã thử AI trả lời được 1 lần
- [ ] Đã đăng nhập, mở sẵn 3 tab, zoom 110–125%
- [ ] Đã tắt thông báo, micro hoạt động
- [ ] Đã copy sẵn tin nhắn mẫu ở cảnh 4 vào Notepad
