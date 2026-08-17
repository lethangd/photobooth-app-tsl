# ĐẶC TẢ UX/UI & KIẾN TRÚC GIẢI PHÁP — HỆ THỐNG PHOTOBOOTH KIOSK TỰ ĐỘNG

**Vai trò:** Senior UX/UI Designer & Solution Architect
**Đối tượng:** Máy Photobooth tự phục vụ 100%, đặt tại khu du lịch, kết nối DSLR/Mirrorless (tethered capture) + máy in nhiệt

---

## 0. GIẢ ĐỊNH & NGUYÊN TẮC THIẾT KẾ NỀN TẢNG

**Giả định kỹ thuật:**
- Màn hình kiosk dạng dọc (portrait, cảm ứng, tỷ lệ ~9:16) — phổ biến với photobooth. Nếu dùng màn ngang, tỷ lệ bố cục cần điều chỉnh lại tương ứng.
- Camera kết nối tethered qua SDK (Canon EDSDK / Sony Camera Remote SDK / gPhoto2), điều khiển shutter từ phần mềm, live-view stream về màn hình.
- Máy chạy **không có nhân viên trông coi** → đây là nguyên tắc chi phối toàn bộ thiết kế lỗi/timeout bên dưới.

**3 nguyên tắc thiết kế xuyên suốt:**

| Nguyên tắc | Ý nghĩa |
|---|---|
| **Fail-safe** | Khách đã thanh toán thì không bao giờ được "mất trắng" — dù lỗi camera/máy in/mạng, ảnh và tiền của khách phải được bảo toàn (lưu local, xử lý nền, gửi bù sau). |
| **Fail-forward** | Mọi trạng thái lỗi đều phải có đường thoát tự động về `IDLE`, không được để máy "treo" chờ nhân viên xử lý. |
| **Recoverable session** | Trạng thái phiên (đã thanh toán, đã chụp, đã chọn...) cần được lưu từng bước (SQLite/local DB) để nếu app crash/mất điện giữa chừng, có thể khôi phục thay vì bắt khách làm lại từ đầu. |

---

## PHẦN 1 — TỐI ƯU & CHUẨN HÓA USER FLOW

### 1.1 Sơ đồ luồng tổng quan

```
[S1 Idle] --chạm màn hình--> [S2 Chọn gói] --chọn N ảnh--> [S3 Thanh toán VietQR]
   --thanh toán OK--> [S4 Chuẩn bị] --auto sau Xs--> [S5 Chụp tự động (N+2 shot)]
   --đủ shot--> [S6 Chọn ảnh (đúng N)] --> [S7 Chọn Filter] --> [S8 Chọn Frame theme]
   --> [S9 Preview & Xác nhận] --in--> [S10 Đang in] --> [S11 QR tải file gốc + timelapse]
   --> [S12 Cảm ơn] --timeout--> [S1 Idle]
```

Mọi màn hình từ S2 trở đi đều có nhánh lỗi/timeout quay về `IDLE` hoặc tự-động-hoá-tiếp-tục (chi tiết Phần 3).

### 1.2 Quyết định thiết kế quan trọng: **Thanh toán trước khi chụp**

Vì máy chạy 100% không người trông, thanh toán nên đặt **ngay sau khi chọn gói, trước khi chụp** (mô hình vending machine) — tránh khách dùng thử camera/xử lý ảnh mà không trả tiền. Phương án thay thế "thanh toán sau khi xem trước, trước khi in" giảm rủi ro lãng phí giấy in nhưng lại mở lỗ hổng cho khách chụp/chỉnh ảnh miễn phí rồi bỏ đi — không phù hợp với vận hành không giám sát. **Khuyến nghị: giữ pay-first.**

### 1.3 Bảng logic nghiệp vụ cốt lõi

| Tham số | Công thức / Giá trị | Ghi chú Admin Config |
|---|---|---|
| `layoutCount` (N) | 2 / 3 / 4 ảnh | Giá tiền riêng từng N, quản lý trong bảng `pricing` |
| `totalShots` | N + `shotBufferCount` | **Không hard-code "+2"** — để admin config `shotBufferCount` (mặc định 2, cho phép 1–3) phòng khi cần đổi tỷ lệ dư sau này |
| `captureCountdownSeconds` | Mặc định 10s/shot | Admin config, khoảng cho phép 5–20s |
| `requiredSelection` | = N | Nút "Tiếp tục" ở S6 chỉ active khi đã chọn đúng N, không hơn không kém |
| `filters[]` | Danh sách filter màu | Admin CRUD, mỗi filter gồm tên + LUT/CSS string + thumbnail + thứ tự hiển thị |
| `frameThemes[]` | Theo địa danh/sự kiện | Admin CRUD, hỗ trợ `validFrom`/`validTo` để hiển thị theo mùa/lễ hội |
| `paymentTimeoutSeconds` | Mặc định 180s | Admin config |
| `downloadLinkExpiryDays` | Mặc định 7 ngày | Admin config |

### 1.4 Gợi ý bổ sung (tùy chọn, không bắt buộc)

- **Chọn ngôn ngữ** (VN/EN/KR/CN...): nếu đặt tại khu du lịch có khách quốc tế, nên thêm màn hình S0 chọn ngôn ngữ, có thể bật/tắt qua Admin (`enableLanguageSelect`). Không bắt buộc theo logic gốc bạn đưa ra nên mình để là tùy chọn.
- **Crop guide khớp tỷ lệ in**: live-view camera nên hiển thị khung crop-guide đúng tỷ lệ khổ in cuối cùng, tránh tình trạng ảnh bị cắt bất ngờ sau khi ghép khung.

---

## PHẦN 2 — ĐẶC TẢ CHI TIẾT TỪNG MÀN HÌNH

### S1. Màn hình chờ (Idle / Attract Loop)

| | |
|---|---|
| **Mục tiêu** | Thu hút khách qua lại, giới thiệu sản phẩm mẫu |
| **State ID** | `IDLE` |
| **Vào từ** | Khởi động app / kết thúc phiên trước / timeout từ bất kỳ màn hình nào |
| **Ra tới** | `PACKAGE_SELECT` |

**Layout & UI:** Video loop hoặc slideshow fullscreen các ảnh mẫu/khung theme đẹp nhất; logo/branding cố định góc trên; CTA lớn dạng pulse animation "Chạm để bắt đầu"; có thể thêm mini badge giá khởi điểm ("Chỉ từ 50.000đ").

**UX & Logic:** Chạm bất kỳ vị trí nào trên màn hình → chuyển `PACKAGE_SELECT`. Đây là trạng thái mặc định mà mọi luồng lỗi/timeout quay về.

**Timeout/Fallback:** Không áp dụng (đây chính là điểm đến của timeout).

---

### S2. Chọn gói / Layout ảnh

| | |
|---|---|
| **Mục tiêu** | Khách chọn số ảnh trong khung (2/3/4), xác định giá và `totalShots` |
| **State ID** | `PACKAGE_SELECT` |
| **Ra tới** | `PAYMENT` (khi chọn) / `IDLE` (timeout) |

**Layout & UI:** 3 card lớn xếp ngang (hoặc dọc nếu portrait hẹp) — mỗi card gồm ảnh mockup layout tương ứng, số ảnh, giá tiền, nút "Chọn gói này"; nút Back góc trên trái → `IDLE`.

**UX & Logic:** Khi chọn → set `selectedLayout = N`, tính `totalShots = N + shotBufferCount`, điều hướng `PAYMENT`.

**Timeout/Fallback:** 60s không thao tác → quay về `IDLE` (chưa mất phí nên an toàn để reset thẳng).

---

### S3. Thanh toán VietQR

| | |
|---|---|
| **Mục tiêu** | Thu tiền theo gói đã chọn trước khi cho phép chụp |
| **State ID** | `PAYMENT` — trạng thái con: `PENDING` / `SUCCESS` / `EXPIRED` / `FAILED` |
| **Ra tới** | `GET_READY` (thành công) / `PACKAGE_SELECT` (hết hạn/hủy) |

**Layout & UI:** QR VietQR động (amount = giá gói, nội dung CK chứa `sessionId` để đối soát tự động), số tiền + tên gói hiển thị rõ, đồng hồ đếm ngược `paymentTimeoutSeconds`, trạng thái "Đang chờ thanh toán..." với spinner, nút "Hủy" quay lại S2.

**UX & Logic:** Poll trạng thái thanh toán mỗi 2–3s qua API (kết hợp webhook từ cổng thanh toán làm nguồn chính, polling làm dự phòng nếu webhook trễ) — đối soát theo `sessionId` trong nội dung chuyển khoản. Nhận `SUCCESS` → tự động chuyển `GET_READY`.

**Timeout/Fallback:** Hết `paymentTimeoutSeconds` không nhận thanh toán → hủy QR, hiển thị "Phiên thanh toán đã hết hạn", quay về S2. Nếu webhook trả lỗi/API lỗi → cho thử tạo QR mới (tối đa 3 lần).

---

### S4. Chuẩn bị / Hướng dẫn tư thế (Get Ready)

| | |
|---|---|
| **Mục tiêu** | Cho khách xem live-view, hướng dẫn vị trí đứng trước khi chụp thật |
| **State ID** | `GET_READY` |
| **Ra tới** | `CAPTURING` (tự động) |

**Layout & UI:** Live-view camera fullscreen với overlay khung silhouette gợi ý vị trí đứng (điều chỉnh theo N người nếu cần), text lớn "Sẽ chụp {totalShots} kiểu, mỗi kiểu {captureCountdownSeconds}s — không cần bấm nút", nút nhỏ "Bắt đầu ngay" cho khách muốn bỏ qua chờ.

**UX & Logic:** Tự động đếm ngược `getReadyDurationSeconds` (mặc định 5s) rồi tự chuyển sang `CAPTURING` — **không bắt buộc khách phải bấm nút**, giữ đúng tinh thần tự động hoá của toàn hệ thống. Nút "Bắt đầu ngay" chỉ để rút ngắn thời gian chờ cho khách đã quen.

**Timeout/Fallback:** Không cần — màn hình này tự tiến, không phụ thuộc thao tác khách.

---

### S5. Chụp ảnh tự động (Capture Sequence)

| | |
|---|---|
| **Mục tiêu** | Chụp tự động đủ `totalShots` = N + buffer ảnh |
| **State ID** | `CAPTURING` |
| **Ra tới** | `PHOTO_SELECT` (đủ shot) |

**Layout & UI:** Live-view fullscreen, đồng hồ đếm ngược lớn giữa màn hình (số to, animation 3-2-1), chỉ số "Kiểu {current}/{totalShots}" góc trên, hiệu ứng flash trắng toàn màn hình đúng lúc trigger shutter (giả lập đèn flash + tạo tín hiệu rõ ràng cho khách biết đã chụp), dải thumbnail nhỏ các ảnh vừa chụp phía dưới.

**UX & Logic:** Hết đếm ngược → gọi lệnh trigger camera qua SDK → ảnh trả về lưu buffer local → tự động bắt đầu đếm ngược cho shot kế tiếp, lặp lại đến khi đủ `totalShots`, hoàn toàn không cần thao tác khách. Sau shot cuối → tự động chuyển `PHOTO_SELECT`.

**Timeout/Fallback:** Nếu camera không phản hồi trong X giây sau lệnh trigger → thử lại tự động tối đa 2 lần cho shot đó; nếu vẫn lỗi → chuyển trạng thái lỗi hệ thống (xem Phần 3), không tự ý bỏ qua shot vì sẽ làm sai `totalShots`.

---

### S6. Chọn ảnh ưng ý (Photo Selection)

| | |
|---|---|
| **Mục tiêu** | Khách chọn đúng N ảnh trong (N + buffer) ảnh đã chụp để gán vào khung |
| **State ID** | `PHOTO_SELECT` |
| **Ra tới** | `FILTER_SELECT` |

**Layout & UI:** Grid hiển thị toàn bộ ảnh đã chụp (thumbnail lớn, dễ chạm), overlay checkmark khi chọn, counter nổi bật "Đã chọn {count}/{N}", nút "Xem lớn" (modal preview) khi giữ/chạm lâu, nút "Tiếp tục" chỉ active khi `count === N`.

**UX & Logic:** Chạm ảnh để toggle chọn/bỏ; nếu đã chọn đủ N mà chạm thêm ảnh khác → chặn (hoặc rung nhẹ nhắc "Đã chọn đủ, bỏ chọn 1 ảnh trước"). Khi đủ N → cho phép "Tiếp tục" → `FILTER_SELECT`.

**Timeout/Fallback:** Vì khách **đã thanh toán**, không được để timeout đẩy về `IDLE` mất trắng ảnh. Sau 45s không thao tác → hiện popup cảnh báo đếm ngược 15s → nếu vẫn không thao tác, **tự động chọn N ảnh đầu tiên theo thứ tự chụp** và tự tiếp tục luồng, tránh kiosk bị treo khi không có nhân viên.

---

### S7. Chọn bộ lọc màu (Filter Selection)

| | |
|---|---|
| **Mục tiêu** | Áp color grading cho N ảnh đã chọn |
| **State ID** | `FILTER_SELECT` |
| **Ra tới** | `FRAME_SELECT` |

**Layout & UI:** Preview carousel N ảnh đã chọn ở trên, dải filter thumbnail cuộn ngang phía dưới (Natural, B&W, Vintage, Vivid, Film...), filter đang chọn có viền highlight.

**UX & Logic:** Áp dụng filter đồng nhất cho cả N ảnh (đơn giản, nhanh, đúng kỳ vọng khách du lịch muốn bộ ảnh đồng bộ) thay vì cho chỉnh từng ảnh riêng — giảm số bước thao tác. Preview real-time (CSS filter / WebGL client-side để không cần round-trip server).

**Timeout/Fallback:** 30s không thao tác → cảnh báo 10s → hết hạn tự áp filter mặc định ("Natural") và tiếp tục.

---

### S8. Chọn khung trang trí (Frame Theme Selection)

| | |
|---|---|
| **Mục tiêu** | Chọn khung/viền theo địa danh hoặc sự kiện |
| **State ID** | `FRAME_SELECT` |
| **Ra tới** | `FINAL_PREVIEW` |

**Layout & UI:** Grid/carousel các theme khung (mỗi item = preview thật đã ghép ảnh khách vào khung, không chỉ mockup rỗng), tab lọc theo danh mục nếu nhiều theme (Địa danh / Lễ hội / Mùa), tên theme hiển thị dưới mỗi thumbnail.

**UX & Logic:** Ghép preview thời gian thực (overlay PNG trong suốt lên ảnh đã chọn+filter) để khách thấy đúng kết quả cuối trước khi xác nhận — tránh bất ngờ ở bước preview cuối.

**Timeout/Fallback:** 30s không thao tác → cảnh báo 10s → hết hạn tự chọn theme mặc định/phổ biến nhất và tiếp tục.

---

### S9. Xem trước & Xác nhận (Final Preview)

| | |
|---|---|
| **Mục tiêu** | Khách xem bản ghép cuối cùng đúng khổ in trước khi in |
| **State ID** | `FINAL_PREVIEW` |
| **Ra tới** | `PRINTING` |

**Layout & UI:** Composite ảnh cuối full screen đúng tỷ lệ khổ in thật, nút "In ngay" nổi bật, nút phụ "Chỉnh lại" (quay lại `FILTER_SELECT` hoặc `FRAME_SELECT`, giữ nguyên lựa chọn ảnh).

**UX & Logic:** Xác nhận → gửi job in tới `PRINTING`, đồng thời **bắt đầu background job dựng video timelapse** từ (N + buffer) ảnh gốc song song (để sẵn sàng khi tới S11, không bắt khách chờ thêm).

**Timeout/Fallback:** 30s không thao tác → tự động xác nhận và in với lựa chọn hiện tại (đã thanh toán, ưu tiên hoàn tất giao dịch hơn là để treo).

---

### S10. Đang in ảnh (Printing)

| | |
|---|---|
| **Mục tiêu** | Thông báo trạng thái in, giữ khách chờ có mục đích |
| **State ID** | `PRINTING` |
| **Ra tới** | `QR_DOWNLOAD` |

**Layout & UI:** Animation ảnh đang in / progress bar, thông điệp "Ảnh của bạn đang được in...". **Đây là thời gian chết ~30–60s rất phù hợp để chèn tính năng UX Innovation #1 (Phần 6)** — QR mời bạn bè vote ảnh đẹp nhất.

**UX & Logic:** Gọi driver/queue máy in nhiệt, theo dõi status (`queued`/`printing`/`done`/`error`) qua polling hoặc callback từ printer service.

**Timeout/Fallback:** Xem Phần 3.2 (máy in hết giấy/kẹt giấy) — quan trọng: **dù in lỗi, khách vẫn phải nhận được QR ở S11** vì đã thanh toán.

---

### S11. Quét QR lấy file gốc + Video Timelapse

| | |
|---|---|
| **Mục tiêu** | Khách quét QR tải toàn bộ ảnh gốc (N + buffer, không chỉ ảnh đã in) + video timelapse |
| **State ID** | `QR_DOWNLOAD` |
| **Ra tới** | `THANK_YOU` |

**Layout & UI:** QR code lớn giữa màn hình, hướng dẫn quét ngắn gọn, ghi rõ hạn link (`downloadLinkExpiryDays`), tùy chọn phụ: nhập SĐT/Zalo để nhận lại link qua SMS (phòng khách quét chưa kịp lưu).

**UX & Logic:** QR trỏ tới trang download (cloud storage — S3/GCS ký sẵn URL có hạn) chứa: toàn bộ ảnh gốc full-res, bộ ảnh đã áp filter/frame, video timelapse (đã dựng nền từ bước S9). Nếu video chưa dựng kịp → trang download hiển thị "video sẽ sẵn sàng sau ít phút, link không đổi".

**Timeout/Fallback:** Hiển thị cố định 60–90s rồi tự chuyển `THANK_YOU` (không phải lỗi — chỉ là hết thời lượng hiển thị, link vẫn còn hiệu lực qua SĐT/Zalo nếu khách đã nhập).

---

### S12. Cảm ơn & Reset (Thank You / End)

| | |
|---|---|
| **Mục tiêu** | Kết thúc phiên, dọn session, quay về trạng thái chờ |
| **State ID** | `THANK_YOU` |
| **Ra tới** | `IDLE` |

**Layout & UI:** Thông điệp cảm ơn + tên địa danh, gợi ý nhẹ "Hẹn gặp lại", có thể chèn logo mạng xã hội của địa điểm.

**UX & Logic:** Sau 8–10s tự động quay `IDLE`. Xoá session tạm ở client, ảnh gốc/video đã upload cloud thì xoá local để giải phóng dung lượng máy.

---

## PHẦN 3 — CƠ CHẾ XỬ LÝ LỖI & TIMEOUT TOÀN HỆ THỐNG

### 3.1 Bảng timeout theo từng màn hình

| Màn hình | Ngưỡng cảnh báo | Ngưỡng timeout | Hành vi khi hết hạn |
|---|---|---|---|
| S2 Chọn gói | — | 60s | Quay `IDLE` (chưa thanh toán, an toàn để reset) |
| S3 Thanh toán | — | `paymentTimeoutSeconds` (180s) | Quay `PACKAGE_SELECT` kèm thông báo hết hạn |
| S6 Chọn ảnh | 45s | +15s | Tự chọn N ảnh đầu tiên, tiếp tục luồng |
| S7 Chọn filter | 30s | +10s | Tự áp filter mặc định, tiếp tục |
| S8 Chọn frame | 30s | +10s | Tự chọn theme mặc định, tiếp tục |
| S9 Preview | 30s | — | Tự xác nhận và in |
| S11 QR download | — | 60–90s (cố định) | Chuyển `THANK_YOU`, không phải lỗi |

**Nguyên tắc chốt:** Trước khi thanh toán (S1–S2) → timeout luôn quay thẳng `IDLE`. Sau khi thanh toán (S4 trở đi) → timeout luôn **tự-động-tiếp-tục với giá trị mặc định**, không bao giờ quay `IDLE` và làm mất giao dịch đã thu tiền.

### 3.2 Ma trận xử lý lỗi

| Lỗi | Điểm phát sinh | Cách phát hiện | Xử lý hệ thống | Hiển thị cho khách |
|---|---|---|---|---|
| Camera mất kết nối | S4, S5 | Heartbeat/SDK callback timeout ~3s | Tự reconnect 2 lần → nếu vẫn lỗi, dừng session, log + cảnh báo admin (Telegram/Email) | "Hệ thống đang gặp sự cố, vui lòng đợi hoặc liên hệ hotline [số]" |
| Thanh toán quá hạn | S3 | Countdown hết, không nhận webhook SUCCESS | Huỷ QR, xoá session tạm | Quay S2, "Phiên thanh toán đã hết hạn" |
| Thanh toán lỗi | S3 | Webhook/API trả FAILED | Cho tạo lại QR mới, tối đa 3 lần | "Thanh toán không thành công, vui lòng thử lại" |
| Máy in hết giấy/mực | S10 | Sensor máy in trả status error | Dừng lệnh in, lưu trạng thái "đã thu tiền, chưa in" vào hàng đợi đối soát | "Máy in gặp sự cố, ảnh của bạn đã được lưu — quét QR bên dưới để nhận file" + vẫn cho qua S11 |
| Máy in kẹt giấy | S10 | Timeout không hoàn tất lệnh in | Retry 1 lần → nếu vẫn lỗi, xử lý như trên | Tương tự trên |
| Mất mạng (không upload được cloud) | S6→S11 | Check kết nối trước upload | Lưu ảnh local, đẩy vào hàng đợi upload nền, retry khi có mạng | Không chặn luồng; QR hiển thị "sẽ sẵn sàng sau ít phút" nếu cần |
| Mất điện / App crash giữa phiên | Bất kỳ | Watchdog service | Tự khởi động lại, khôi phục session gần nhất từ local DB nếu đã thanh toán | Nếu khách đã rời đi: session tự đóng sau vài phút, ảnh vẫn xử lý nền, gửi qua SĐT/Zalo nếu đã nhập ở S11 |

---

## PHẦN 4 — CẤU HÌNH ADMIN PANEL

| Tham số | Mô tả | Kiểu dữ liệu | Mặc định |
|---|---|---|---|
| `pricing` | Giá theo từng gói layout (2/3/4) | `Map<int, VND>` | 50k / 70k / 90k |
| `shotBufferCount` | Số ảnh dư so với layout | `int` | 2 |
| `captureCountdownSeconds` | Đếm ngược mỗi shot | `int (s)` | 10 |
| `getReadyDurationSeconds` | Thời gian hiển thị S4 trước khi tự chụp | `int (s)` | 5 |
| `paymentTimeoutSeconds` | Thời gian chờ thanh toán tối đa | `int (s)` | 180 |
| `filters[]` | Danh sách filter (tên, LUT/CSS, thumbnail, thứ tự) | `Array` | — |
| `frameThemes[]` | Danh sách khung (tên, overlay PNG, địa danh/sự kiện, `validFrom`/`validTo`) | `Array` | — |
| `downloadLinkExpiryDays` | Hạn link tải file gốc | `int` | 7 |
| `printerRetryCount` | Số lần thử lại khi lỗi in | `int` | 1 |
| `supportHotline` | SĐT hỗ trợ hiển thị khi lỗi | `string` | — |
| `bankAccountInfo` | Thông tin tài khoản nhận tiền cho VietQR | `object` | — |
| `enableLanguageSelect` | Bật/tắt màn hình chọn ngôn ngữ | `boolean` | false |

---

## PHẦN 5 — GỢI Ý KIẾN TRÚC KỸ THUẬT (SOLUTION ARCHITECT NOTES)

- **Quản lý luồng kiosk:** Nên mô hình hoá thành **Finite State Machine** tường minh (state + transition + guard rõ ràng, ví dụ dùng XState phía frontend) thay vì if-else lồng nhau — mỗi state ở Phần 2 map thẳng 1-1 vào 1 FSM state, giúp log lại lịch sử transition để debug khi máy tại hiện trường gặp lỗi mà không có ai bên cạnh.
- **Tách camera/printer khỏi UI process:** Theo hướng Clean Architecture bạn đang quen dùng — đóng gói use case `CaptureImage` / `PrintJob` thành service riêng (giao tiếp qua IPC/local API), để có thể đổi SDK camera hoặc model máy in sau này mà không đụng vào UI layer.
- **Resilience cho vận hành không người trông:** watchdog tự restart app nếu treo; hàng đợi upload nền (local-first, retry khi có mạng) cho ảnh gốc/video; cache local toàn bộ asset filter/frame để không phụ thuộc mạng khi render preview.
- **Thanh toán:** VietQR động nên qua cổng hỗ trợ webhook (Casso, SePay, hoặc API ngân hàng trực tiếp nếu có) + polling dự phòng khi webhook trễ, đối soát theo `sessionId` gắn trong nội dung chuyển khoản.
- **Video timelapse:** dựng ở background job queue (không block UI), kích hoạt ngay khi khách vào `FINAL_PREVIEW` để sẵn sàng lúc tới `QR_DOWNLOAD`.

---

## PHẦN 6 — ĐỀ XUẤT TÍNH NĂNG ĐỘT PHÁ (UX INNOVATIONS)

### 1. Photo Battle — Bình chọn ảnh cùng bạn bè trong lúc chờ in

Ở màn hình `PRINTING` (S10) — vốn là thời gian chết 30–60s — hiển thị thêm 1 QR mời khách gửi cho bạn bè (ở xa cũng tham gia được) để vote ảnh đẹp nhất trong toàn bộ (N + buffer) ảnh gốc, không giới hạn ở N ảnh đã chọn in. Ảnh được vote cao nhất có thể unlock 1 bản in phụ miễn phí — tạo động lực chia sẻ thật (mỗi lượt vote = một người ngoài nhìn thấy sản phẩm/địa danh). Đây là cơ chế viral hiệu quả hơn hẳn share ảnh đơn thuần vì nó **chủ động kéo người thứ ba vào tương tác**, không chỉ dừng ở khách đang đứng trước máy.

### 2. Gói xuất bản mạng xã hội tự động (Auto Social-Ready Export)

Song song lúc dựng video timelapse, tự động render sẵn 2–3 bản xuất chuẩn dọc 9:16 (TikTok/Reels/Story) kèm nhạc nền không bản quyền đổi theo theme địa danh, và caption/hashtag gợi ý tự động (tên địa danh + hashtag trend). Khách chỉ cần tải về và đăng ngay — giảm ma sát chia sẻ (friction) xuống mức tối thiểu, vì rào cản lớn nhất khiến khách không đăng bài thường là "phải tự edit". Loại bỏ bước đó = tăng tỷ lệ đăng thật sự.

### 3. Souvenir Digital Passport — Hành trình sưu tập đa điểm

Nếu về sau bạn đặt nhiều máy tại nhiều điểm trong cùng khu du lịch: gắn 1 định danh khách (QR cá nhân hoặc SĐT/Zalo) dùng xuyên suốt, để mỗi lần chụp ở các điểm khác nhau được gộp vào 1 "album hành trình" online. Cuối chuyến hệ thống tự ghép thành 1 video/collage tổng hợp cả hành trình. Tính năng này vừa tăng doanh thu (khách có động lực chụp ở nhiều điểm hơn), vừa tạo ra nội dung chia sẻ dài hơi hơn — 1 video hành trình cả ngày viral tốt hơn nhiều so với 1 tấm ảnh đơn lẻ.

*(Bonus, chưa triển khai chi tiết): khung ảnh phản ứng theo thời tiết/giờ thực tế tại địa điểm — ví dụ frame riêng cho trời mưa hoặc hoàng hôn — tạo cảm giác "độc bản, chỉ có hôm nay" thúc đẩy khách chụp lại lần sau.*
