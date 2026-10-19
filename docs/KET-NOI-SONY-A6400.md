# Kết nối máy ảnh Sony a6400 với photobooth

Hướng dẫn này giải thích **vì sao cắm a6400 vào laptop mà phần mềm chưa nhận**, rồi đi từng bước để nối máy cho đúng, cấu hình phần mềm và kiểm tra.

---

## 1. Vì sao cắm vào mà chưa nhận camera

Kết quả kiểm tra trên laptop của bạn:

- Windows **chưa từng thấy thiết bị nào của Sony** (mã hãng USB `054C`).
- Không có card ghi hình HDMI nào.
- Phần mềm chỉ thấy webcam laptop **"HP Wide Vision HD Camera"**.

Có hai nguyên nhân chồng lên nhau:

1. **Cắm thẳng a6400 bằng cáp USB thì máy ảnh không tự thành webcam.** Qua USB, a6400 chỉ hiện ra như ổ chứa ảnh (để chép ảnh) hoặc chế độ điều khiển từ máy tính. Muốn phần mềm dùng được, cần **một trong hai cách** ở mục 2.
2. **Windows chưa thấy cả kết nối USB**, nghĩa là ngay cả phần "ổ chứa ảnh" cũng chưa hiện. Thường do:
   - cáp **chỉ sạc được, không truyền dữ liệu** (rất hay gặp với cáp micro USB đi kèm sạc dự phòng);
   - máy ảnh **đang tắt** (a6400 phải bật nguồn mới kết nối);
   - cắm qua hub/cổng lỏng, hoặc cắm vào cổng chỉ có điện.

---

## 2. Chọn cách nối

| | **Cách A: Card ghi hình HDMI** (khuyến nghị) | **Cách B: Cáp USB + Sony Imaging Edge Webcam** |
|---|---|---|
| Cần mua | Card ghi hình HDMI→USB, cáp micro HDMI | Không (chỉ cần cáp USB dữ liệu) |
| Chất lượng ảnh | **1920×1080**, mượt 30–60 hình/giây | Khoảng **1024×576**, thấp hơn rõ rệt |
| Độ ổn định | Rất ổn định, chạy cả ngày | Phụ thuộc phần mềm Sony, đôi khi phải cắm lại |
| Dùng khi | Mở bán thật | Thử ngay hôm nay khi chưa có card ghi hình |

Cả hai cách đều làm Windows thấy a6400 như **một webcam**, sau đó phần mềm photobooth cấu hình giống nhau (mục 5).

> Ảnh chụp theo cả hai cách đều lấy từ hình xem trước của máy ảnh. Ảnh 24 MP đầy đủ của a6400 cần bộ SDK riêng của Sony, phần mềm hiện chưa hỗ trợ.

---

## 3. Cách A: Card ghi hình HDMI (khuyến nghị)

### 3.1. Cần chuẩn bị

| Thứ | Ghi chú |
|---|---|
| Card ghi hình HDMI → USB | Loại hỗ trợ 1080p, cổng USB 3.0 (ví dụ Elgato Cam Link 4K, UGREEN / Hagibis HDMI capture USB 3.0) |
| Cáp **micro HDMI (đầu loại D) ↔ HDMI** | a6400 dùng cổng **micro HDMI**, không phải mini HDMI |
| Pin giả **NP‑FW50** + adapter | Để máy chạy cả ngày (ví dụ Sony AC‑PW20 hoặc loại tương thích) |

### 3.2. Đấu nối

```
 Sony a6400 ──(cáp micro HDMI → HDMI)──▶ Card ghi hình ──(USB 3.0)──▶ Laptop
     ▲
  Pin giả NP-FW50 cắm điện
```

1. Gắn pin giả, cắm adapter vào ổ điện.
2. Cắm đầu **micro HDMI** vào cổng HDMI của a6400 (cổng bên hông, dưới nắp cao su).
3. Cắm đầu HDMI lớn vào card ghi hình.
4. Cắm card ghi hình vào cổng **USB 3.0 (màu xanh hoặc có ký hiệu SS)** của laptop, **cắm trực tiếp**, không qua hub không nguồn.
5. **Bật máy ảnh.**

### 3.3. Cài đặt trên máy ảnh

Menu có thể khác đôi chút theo phiên bản firmware.

1. **Xoay vòng chế độ sang Movie** (biểu tượng cuộn phim). **Bắt buộc**: ở chế độ chụp ảnh, máy xuất ảnh 3:2 nằm giữa khung 16:9, hai bên có viền đen. Chỉ dùng chế độ này để xuất hình, không cần bấm quay.
2. **MENU → Setup (hộp đồ nghề) → HDMI Settings**:
   - **HDMI Resolution**: **1080p** (không chọn 2160p hay 1080i).
   - **HDMI Info. Display**: **Off** (hình sạch, không có chữ và khung lấy nét).
   - **TC Output**: Off.
   - **CTRL FOR HDMI**: Off.
3. **Auto Power OFF Temp.**: **High**.
4. **Power Save Start Time**: thời gian dài nhất.
5. Lấy nét **AF‑C**, bật **Face/Eye AF** (ưu tiên mặt người).
6. Phơi sáng theo đèn của tiệm: ví dụ ISO 200–400, khẩu f/5.6–f/8, cân bằng trắng cố định theo đèn.

### 3.4. Kiểm tra Windows đã thấy card ghi hình

1. Mở app **Camera** của Windows → bấm nút đổi camera → phải thấy hình từ a6400.
2. **Đóng app Camera** ngay sau đó (hai phần mềm không dùng chung một camera được).
3. Hoặc chạy script kiểm tra ở mục 6: phần "Camera / card ghi hình" phải có một dòng mới (thường tên **"USB Video"**, **"Cam Link 4K"**…).

Nếu chưa thấy: xem bảng sự cố ở mục 7.

---

## 4. Cách B: Cáp USB + Sony Imaging Edge Webcam (thử nhanh)

### 4.1. Cần chuẩn bị

- Cáp **micro USB có truyền dữ liệu**. Cách thử: cắm điện thoại Android cũ vào máy tính bằng chính cáp đó, nếu máy tính thấy điện thoại thì cáp truyền được dữ liệu.
- Phần mềm **Sony Imaging Edge Webcam** (miễn phí, tải từ trang hỗ trợ của Sony, tìm "Imaging Edge Webcam").

### 4.2. Các bước

1. Cài **Imaging Edge Webcam**, sau đó **khởi động lại máy tính**.
2. Trên máy ảnh: **MENU → Setup → USB Connection → PC Remote**.
3. (Nếu có mục này) **MENU → Setup → USB LUN Setting → Multi**.
4. Cắm cáp micro USB từ máy ảnh vào laptop, **bật máy ảnh**. Màn hình máy ảnh hiện chữ kiểu "Connecting / PC Remote".
5. Mở app **Camera** của Windows → đổi camera → phải thấy **"Imaging Edge Webcam"** có hình → đóng app Camera.

Nếu Imaging Edge Webcam không nhận máy: cập nhật **firmware a6400** lên bản mới nhất (trang hỗ trợ của Sony), rồi làm lại từ bước 2.

---

## 5. Cấu hình phần mềm photobooth

Làm sau khi mục 3.4 hoặc 4.2 đã thấy hình trong app Camera.

1. **Đóng app Camera, OBS, Zoom, Teams…** (mọi thứ đang dùng camera).
2. Chạy phần mềm (`run-local.bat`).
3. Chạy script kiểm tra (mục 6), xem phần **"Camera phần mềm photobooth mở được"**, ghi lại **đúng tên** card ghi hình hoặc "Imaging Edge Webcam".
4. Mở **`http://127.0.0.1:8000/classic#/admin/config`**, đăng nhập bằng mật khẩu admin (trong file `.env`).
5. Vào mục **Cameras**:
   1. Trong danh sách **group_backends**, sửa backend đầu tiên (đang là *virtual camera*), hoặc thêm một backend mới:
      - **backend_type**: **WebcamPyav**.
      - **device_identifier**: chọn trong danh sách đúng tên ở bước 3.
      - **cam_resolution_width / height**: **1920 / 1080** với cách A; **1024 / 576** với cách B.
      - **cam_framerate**: **30**.
      - **pixel_format**: **auto**.
      - **enabled**: bật.
   2. **index_backend_stills** và **index_backend_video**: số thứ tự của backend vừa sửa (backend đầu tiên là **0**).
6. Bấm **Save**.
7. **Tắt hẳn phần mềm** (đóng cửa sổ dòng lệnh) rồi chạy lại `run-local.bat`.

### Kiểm tra

- Mở **`http://127.0.0.1:8000/api/framebooth/camera-status`**, phải thấy:
  ```json
  {"available": true, "virtual": false}
  ```
  - `"virtual": true`: phần mềm vẫn dùng camera ảo, cấu hình chưa được lưu hoặc chưa khởi động lại.
  - `"available": false`: phần mềm không mở được camera (mục 7).
- Đi một phiên thử (nhân viên nhập PIN): màn **"Sẵn sàng chưa?"** hiện hình từ a6400, **không** có chữ "Camera thiết bị" ở góc (chữ đó nghĩa là đang dùng webcam laptop dự phòng).
- Ảnh chụp **không có viền đen** hai bên, đúng màu, đủ nét.
- Video timelapse trong mã QR có cảnh khách tạo dáng.

---

## 6. Script kiểm tra camera

Trong thư mục dự án có **`tools\kiem-tra-camera.ps1`**. Chạy mỗi khi cắm lại máy ảnh hoặc thấy kiosk không nhận camera:

- Chuột phải file → **Run with PowerShell**, hoặc
- Mở PowerShell trong thư mục dự án và chạy:
  ```powershell
  powershell -ExecutionPolicy Bypass -File tools\kiem-tra-camera.ps1
  ```

Script in ra 4 phần:

| Phần | Ý nghĩa | Kết quả mong đợi |
|---|---|---|
| 1. Thiết bị Sony đang cắm | Windows có thấy a6400 qua USB không (chỉ cách B) | Cách B: có dòng Sony. Cách A: không cần |
| 2. Camera / card ghi hình | Windows thấy những camera nào | Có thêm card ghi hình (cách A) hoặc Imaging Edge Webcam (cách B) bên cạnh webcam HP |
| 3. Camera phần mềm mở được | Tên dùng cho *device_identifier* ở mục 5 | Có tên card ghi hình / Imaging Edge Webcam |
| 4. Trạng thái camera của kiosk | Phần mềm đang dùng camera nào | `available = True, virtual = False` |

---

## 7. Sự cố thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Script báo **"Windows chưa từng thấy máy Sony"** (cách B) | Cáp chỉ sạc; máy ảnh tắt; USB Connection chưa đặt PC Remote | Đổi cáp dữ liệu; bật máy; làm lại mục 4.2 bước 2–4 |
| App Camera **không có card ghi hình** (cách A) | Cắm cổng USB 2.0 hoặc qua hub; card cần cổng USB 3.0 | Cắm thẳng cổng USB 3.0 trên laptop; thử cổng khác |
| Card ghi hình có trong danh sách nhưng **màn hình đen / "No signal"** | Máy ảnh tắt; cáp HDMI lỏng; HDMI Resolution đặt 2160p hoặc 1080i | Bật máy; cắm chặt micro HDMI; đặt **1080p** (mục 3.3) |
| Hình có **chữ, khung lấy nét, thanh pin** | HDMI Info. Display đang On | Đặt **Off** |
| Ảnh có **viền đen hai bên** | Máy đang ở chế độ chụp ảnh | Xoay vòng chế độ sang **Movie**. Phần mềm vẫn tự cắt viền đen, nhưng ảnh nhỏ hơn |
| `camera-status` báo **`"virtual": true`** | Chưa cấu hình backend WebcamPyav, hoặc chưa khởi động lại | Làm lại mục 5 bước 5–7 |
| `camera-status` báo **`"available": false`**, log có **"cannot open camera"** | Sai *device_identifier*; app khác đang giữ camera; card không hỗ trợ định dạng | Chọn đúng tên ở mục 6 phần 3; đóng app Camera/OBS/Zoom; đổi **pixel_format** sang `yuyv422` hoặc `nv12`; đặt **cam_framerate** 30 |
| Kiosk hiện chữ **"Camera thiết bị"** khi chụp | Camera máy chủ lỗi nên kiosk dùng webcam laptop dự phòng | Xem `camera-status` và log trong thư mục `log/` |
| Hình HDMI **tự tắt sau một lúc** | Máy ảnh tự tắt nguồn / quá nhiệt | Power Save dài nhất; Auto Power OFF Temp **High**; dùng pin giả; để máy thoáng |
| Hình **giật, trễ** | Cắm USB 2.0; laptop yếu | Cắm USB 3.0; đặt cam_framerate 30; tắt hiệu ứng "Hạt film" trong Cài đặt |

Khi cần nhờ hỗ trợ kỹ thuật, gửi kèm:

1. ảnh chụp kết quả script `tools\kiem-tra-camera.ps1`;
2. file log mới nhất trong thư mục `log/`.

---

*Xem thêm:* [HUONG-DAN-TRIEN-KHAI-PHOTOBOOTH.md](HUONG-DAN-TRIEN-KHAI-PHOTOBOOTH.md), mục 8 (camera) và mục 17 (sự cố).
