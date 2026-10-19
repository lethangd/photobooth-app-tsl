# Hướng dẫn triển khai máy photobooth TSL từ một chiếc laptop

Tài liệu này đi từ tổng quan đến chi tiết: cần mua gì, đấu nối ra sao, cài phần mềm từng bước, kiểm tra trước khi mở cửa và vận hành hằng ngày. Đọc lần lượt từ trên xuống; mỗi bước có phần **Kiểm tra** để biết đã làm đúng chưa trước khi sang bước sau.

> Giá trong tài liệu là **mức tham khảo** (thị trường Việt Nam, 2026) để lập ngân sách. Hãy so giá thực tế trước khi mua.

---

## Mục lục

1. [Máy photobooth hoạt động thế nào](#1-máy-photobooth-hoạt-động-thế-nào)
2. [Cần mua thêm những gì](#2-cần-mua-thêm-những-gì)
3. [Ba cấu hình theo ngân sách](#3-ba-cấu-hình-theo-ngân-sách)
4. [Bố trí và đấu nối](#4-bố-trí-và-đấu-nối)
5. [Chuẩn bị Windows trên laptop](#5-chuẩn-bị-windows-trên-laptop)
6. [Cài và chạy phần mềm](#6-cài-và-chạy-phần-mềm)
7. [Cấu hình trong trang quản trị](#7-cấu-hình-trong-trang-quản-trị)
8. [Camera](#8-camera)
9. [Máy in](#9-máy-in)
10. [Thanh toán chuyển khoản tự động](#10-thanh-toán-chuyển-khoản-tự-động)
11. [Ảnh số qua QR (Cloudflare R2)](#11-ảnh-số-qua-qr-cloudflare-r2)
12. [Khung ảnh](#12-khung-ảnh)
13. [Chế độ kiosk: tự bật khi mở máy, toàn màn hình](#13-chế-độ-kiosk-tự-bật-khi-mở-máy-toàn-màn-hình)
14. [Lắp đặt vật lý từng bước](#14-lắp-đặt-vật-lý-từng-bước)
15. [Kiểm tra trước khi mở cửa](#15-kiểm-tra-trước-khi-mở-cửa)
16. [Vận hành hằng ngày](#16-vận-hành-hằng-ngày)
17. [Xử lý sự cố thường gặp](#17-xử-lý-sự-cố-thường-gặp)
18. [Sao lưu và bảo mật](#18-sao-lưu-và-bảo-mật)
19. [Lộ trình nâng cấp](#19-lộ-trình-nâng-cấp)

---

## 1. Máy photobooth hoạt động thế nào

Toàn bộ phần mềm chạy **trên chính chiếc laptop**, không cần thuê máy chủ. Laptop là "bộ não": nó điều khiển camera, hiển thị màn hình cảm ứng cho khách, gửi lệnh in, và đẩy ảnh số lên mạng để khách quét QR tải về.

```
                         ┌──────────────── Internet (Wi-Fi / 4G) ────────────────┐
                         │                                                        │
                 Cloudflare R2                                                SePay
            (lưu ảnh số 7 ngày,                                    (báo tiền chuyển khoản
             khách quét QR tải)                                       về kiosk, tuỳ chọn)
                         ▲                                                        ▲
                         │                                                        │
  ┌──────────┐   USB   ┌─┴────────────────────────────────────────────────────────┴─┐   USB   ┌──────────┐
  │  Camera  │────────▶│                        LAPTOP                              │────────▶│  Máy in  │
  └──────────┘         │  photobooth-app (http://127.0.0.1:8000)                    │         └──────────┘
                       │  Chrome chế độ kiosk: màn khách  ·  /admin: màn chủ tiệm    │
  ┌──────────┐  HDMI   │                                                            │
  │Màn cảm   │◀────────│                                                            │
  │ứng (khách│────────▶│  (cáp USB của màn cảm ứng gửi thao tác chạm về laptop)     │
  └──────────┘   USB   └────────────────────────────────────────────────────────────┘
```

Một phiên của khách: **chạm màn hình → chọn khung → thanh toán (QR chuyển khoản hoặc nhân viên nhập PIN) → chuẩn bị → chụp → chọn ảnh → chọn màu, khung, trang trí → in → quét QR nhận ảnh số → cảm ơn**.

Trang quản trị cho chủ tiệm: mở `http://127.0.0.1:8000/admin` trên laptop (hoặc trên điện thoại cùng mạng, xem mục 16). Ở đó xem doanh thu, lịch sử phiên, máy in, khung ảnh và cài đặt.

---

## 2. Cần mua thêm những gì

Bạn đã có laptop. Dưới đây là danh sách theo mức độ cần thiết.

### 2.1. Bắt buộc

| Thiết bị | Vì sao cần | Gợi ý | Giá tham khảo |
|---|---|---|---|
| **Màn hình cảm ứng** | Khách tự thao tác; màn laptop quá nhỏ và không cảm ứng | Màn di động 15,6" cảm ứng (cổng USB‑C hoặc HDMI + USB). Lắp lâu dài nên chọn 21,5–24" cảm ứng | 3–5 triệu (15,6"), 6–10 triệu (21,5–24") |
| **Máy in ảnh** | Sản phẩm chính khách mang về | Khởi đầu: **Canon SELPHY CP1500** (in nhiệt thăng hoa, 4×6", không phai, không cần mực nước) | 3,5–4,5 triệu máy; ~5–7 nghìn/tờ |
| **Đèn** | Ảnh sáng đều quyết định 70% chất lượng; webcam rất kém khi thiếu sáng | 1–2 đèn LED softbox hoặc 1 đèn vòng 18" có điều chỉnh độ sáng và nhiệt màu | 1–3 triệu |
| **Phông nền** | Ảnh gọn, đẹp, đúng phong cách tiệm | Phông vải/giấy 2×2 m + giá treo chữ U, hoặc vách trang trí cố định | 0,5–2 triệu |
| **Ổ cắm có cầu chì + dây nguồn dài** | Cấp điện an toàn cho laptop, màn, máy in, đèn | Ổ 6 lỗ có công tắc, chống sét lan truyền | 0,3–0,6 triệu |

### 2.2. Nên có ngay từ đầu

| Thiết bị | Vì sao | Gợi ý | Giá tham khảo |
|---|---|---|---|
| **Webcam rời 1080p trở lên** | Webcam laptop thường mờ, nhiễu, góc sai. Webcam rời đặt được đúng tầm mắt | Logitech C920/C922 (1080p) hoặc Logitech Brio (4K) | 1,5–5 triệu |
| **Bộ lưu điện (UPS)** | Mất điện giữa phiên vẫn in xong, không hỏng dữ liệu | UPS 1000–1500 VA | 1,5–3 triệu |
| **Hub USB có nguồn riêng** | Laptop ít cổng; camera và màn cảm ứng cần nguồn ổn định | Hub 4–7 cổng USB 3.0 có adapter | 0,3–0,8 triệu |
| **Chân đỡ màn hình / chân camera** | Cố định màn và camera đúng chiều cao | Chân màn hình đứng sàn VESA, tripod 1,6–1,8 m cho camera | 0,5–2 triệu |
| **Mạng ổn định** | Ảnh số qua QR và tự xác nhận chuyển khoản cần Internet | Wi‑Fi của tiệm, hoặc bộ phát 4G làm dự phòng | 0,5–1,5 triệu (bộ phát 4G) |

### 2.3. Nâng cấp khi đã có khách (tuỳ chọn)

| Thiết bị | Vì sao | Gợi ý | Giá tham khảo |
|---|---|---|---|
| **Máy ảnh thay webcam** | Ảnh nét, màu đẹp, xoá phông, khác biệt rõ so với webcam | Canon/Nikon được **digiCamControl** hỗ trợ (ví dụ Canon EOS 200D, M50; Nikon D3500…) + **pin giả** (dummy battery) cắm điện | 8–18 triệu (máy cũ + ống kit) |
| **Máy in chuyên nghiệp** | In nhanh (~10–15 giây/tờ), cuộn giấy 400–700 tờ, chi phí/tờ thấp, cắt được dải 2×6" | DNP DS‑RX1HS / DS620, Citizen CX‑02 | 25–45 triệu |
| **Vỏ kiosk** | Gọn, giấu dây, chống va đập, nhìn chuyên nghiệp | Đặt đóng gỗ/mica theo kích thước màn + camera, hoặc mua vỏ photobooth có sẵn | 3–15 triệu |
| **Màn hình phụ hướng ra ngoài** | Chạy hình mẫu thu hút khách đi ngang | Màn TV cũ + chế độ trình chiếu | tuỳ |

### 2.4. Tài khoản và dịch vụ

| Dịch vụ | Dùng để | Chi phí |
|---|---|---|
| **Tài khoản ngân hàng** của tiệm | Nhận tiền qua mã VietQR | Miễn phí |
| **SePay** (sepay.vn) | Báo cho kiosk khi tiền chuyển khoản về để tự mở phiên chụp | Có gói miễn phí giới hạn giao dịch, gói trả phí theo tháng |
| **Cloudflare R2** (bạn đã tạo) | Lưu ảnh số 7 ngày cho khách quét QR tải | Gần như 0đ ở quy mô một kiosk (10 GB miễn phí/tháng) |

### 2.5. Vật tư tiêu hao

- Giấy in và băng mực theo đúng máy in (SELPHY: bộ KP‑108IN = 108 tờ 4×6 kèm mực).
- Đạo cụ: kính, mũ, bảng chữ, băng đô… (khách rất thích, tăng số ảnh chụp lại).
- Khăn lau màn hình, cồn lau, dây rút buộc cáp, băng keo vải dán dây xuống sàn.

---

## 3. Ba cấu hình theo ngân sách

| | **A. Chạy thử** | **B. Mở bán** (khuyến nghị) | **C. Chuyên nghiệp** |
|---|---|---|---|
| Camera | Webcam laptop | Webcam rời 1080p/4K | Máy ảnh qua digiCamControl |
| Màn khách | Màn laptop hoặc màn cảm ứng 15,6" | Màn cảm ứng 21,5–24" | Màn cảm ứng 24" trong vỏ kiosk |
| Máy in | Canon SELPHY CP1500 | Canon SELPHY CP1500 (mua thêm 1 máy dự phòng) | DNP DS‑RX1HS / Citizen CX‑02 |
| Đèn | 1 đèn vòng | 2 softbox LED | 2 softbox + 1 đèn tóc |
| Khác | — | UPS, hub USB, chân đỡ, phông | Vỏ kiosk, UPS, 4G dự phòng |
| **Tổng thêm (ước tính)** | **~8–12 triệu** | **~18–30 triệu** | **~60–100 triệu** |

Khuyến nghị: bắt đầu bằng **B**. Phần mềm không cần đổi gì khi lên **C**, chỉ đổi cấu hình camera và lệnh in.

---

## 4. Bố trí và đấu nối

### 4.1. Mặt bằng (nhìn từ trên xuống)

```
          Phông nền (rộng ≥ 2 m)
   ┌──────────────────────────────────┐
   │                                  │
   │        Khu khách đứng            │   ← khách cách phông 0,5–1 m
   │        (rộng 1,5–2 m)            │
   │                                  │
   └──────────────────────────────────┘
                 ↑  1,5–2,5 m
   💡 Đèn trái          📷 Camera          💡 Đèn phải
    (chéo 45°)     ┌─────────────────┐      (chéo 45°)
                   │ Màn cảm ứng     │
                   │ (ngay dưới cam) │
                   └─────────────────┘
                   Bàn/kệ: laptop + máy in (khách lấy ảnh ở khay ra)
```

Nguyên tắc:

- **Camera ở tầm mắt** (cao ~1,5–1,6 m tính tới ống kính), **ngay trên màn hình** để khách nhìn màn cũng là nhìn ống kính. Màn kiosk có dòng "Camera ở ngay phía trên màn hình".
- **Khoảng cách camera → khách 1,5–2,5 m**: đủ cho nhóm 2–4 người. Nhóm đông thì lùi xa hơn.
- **Hai đèn chéo 45°**, cao hơn đầu khách một chút, chĩa xuống nhẹ. Tránh đèn chiếu thẳng sau lưng khách (ngược sáng) và tránh cửa kính sau lưng khách.
- **Máy in nằm chỗ khách lấy được ảnh** nhưng không với tới laptop.
- Đi dây sát tường, dán băng keo vải các đoạn chạy qua lối đi.

### 4.2. Đấu nối

| Nối | Cáp | Ghi chú |
|---|---|---|
| Màn cảm ứng → laptop (hình) | HDMI hoặc USB‑C (DisplayPort) | Màn di động USB‑C có thể dùng 1 cáp cho cả hình và cảm ứng |
| Màn cảm ứng → laptop (chạm) | USB‑A ↔ USB‑B / USB‑C | **Bắt buộc**, thiếu cáp này thì màn chỉ hiển thị, không chạm được |
| Webcam / máy ảnh → laptop | USB (nên cắm thẳng vào laptop hoặc hub có nguồn) | Máy ảnh: dùng pin giả cắm điện, không dùng pin thường |
| Máy in → laptop | USB | Cài driver trước khi cắm (mục 9) |
| Laptop, màn, máy in, đèn → nguồn | Ổ cắm sau UPS | Đèn có thể cắm ngoài UPS để tiết kiệm dung lượng UPS |

### 4.3. Thiết lập hai màn hình trên Windows

Nếu laptop mở nắp và dùng thêm màn cảm ứng:

1. `Win + P` → chọn **Second screen only** (chỉ màn phụ), hoặc **Extend** nếu muốn giữ màn laptop cho chủ tiệm.
2. Khi dùng Extend: **Settings → System → Display** → chọn màn cảm ứng → bật **Make this my main display**, để Chrome kiosk mở trên màn khách.
3. Nếu chạm vào màn khách mà con trỏ nhảy sang màn laptop: **Control Panel → Tablet PC Settings → Setup** → chọn **Touch input** rồi chạm vào đúng màn khách theo hướng dẫn.

**Kiểm tra:** chạm vào nút Start trên màn cảm ứng thì menu Start mở ra đúng trên màn đó.

---

## 5. Chuẩn bị Windows trên laptop

Làm một lần, giúp máy chạy cả ngày không bị ngắt.

1. **Cập nhật Windows và driver** đầy đủ trước ngày mở bán (để không tự cập nhật giữa ca).
2. **Không cho máy ngủ:** Settings → System → Power → *Screen and sleep*: đặt **Never** cho cả "When plugged in". Chọn chế độ **Best performance**.
3. **Gập nắp không tắt máy** (nếu đóng nắp laptop khi chạy màn ngoài): Control Panel → Power Options → *Choose what closing the lid does* → **Do nothing** khi cắm sạc.
4. **Hoãn Windows Update trong giờ mở cửa:** Settings → Windows Update → *Advanced options* → **Active hours** đặt theo giờ mở cửa, và **Pause updates** trong mùa cao điểm.
5. **Tắt thông báo:** Settings → System → Notifications → tắt, bật **Do not disturb**.
6. **Tắt cử chỉ vuốt cạnh màn hình** (khách vuốt nhầm sẽ mở bảng thông báo): Settings → Bluetooth & devices → Touch → tắt **Three- and four-finger touch gestures**. Với màn cảm ứng rời, cần thêm bước chỉnh registry để tắt vuốt cạnh (*AllowEdgeSwipe = 0*), nhờ kỹ thuật làm nếu cần.
7. **Tạo tài khoản Windows riêng cho kiosk** (khuyến nghị): tài khoản thường, không quyền admin, tự đăng nhập. Chủ tiệm giữ tài khoản admin riêng.
8. **Tắt các app tự chạy dùng camera** (Zoom, Teams, Camera, Skype…): Task Manager → Startup apps → Disable. Hai app cùng dùng camera là nguyên nhân số 1 khiến kiosk "không mở được camera".

**Kiểm tra:** để máy yên 30 phút: màn hình không tắt, không có thông báo bật lên.

---

## 6. Cài và chạy phần mềm

### 6.1. Cài các phần cần thiết

1. **Python 3.11** (64-bit) từ python.org. Khi cài, tick **Add python.exe to PATH**.
2. **Google Chrome** (để chạy màn khách ở chế độ kiosk).
3. **Git** (nếu lấy mã nguồn từ kho Git). Có thể chép nguyên thư mục dự án bằng USB thay cho Git.
4. Node.js và pnpm **không cần** trên máy kiosk: giao diện đã được build sẵn trong `src/web/frontend`. Chỉ máy dùng để sửa giao diện mới cần.

### 6.2. Đặt thư mục dự án

Chép thư mục `photobooth-app-tsl` vào một nơi cố định, ví dụ `D:\photobooth-app-tsl`. Không đặt trong Desktop hay OneDrive (OneDrive đồng bộ có thể khoá file khi đang chạy).

### 6.3. Tạo file `.env`

File `.env` giữ **mật khẩu và khoá bí mật**. File này không được đưa lên Git.

1. Trong thư mục dự án, chép `.env.example` thành `.env` (nếu chưa có).
2. Mở `.env` bằng Notepad và điền:

```ini
ADMIN_PASSWORD=đặt-mật-khẩu-admin-ít-nhất-6-ký-tự
STAFF_PIN=4-chữ-số-cho-nhân-viên
AUTH_TOKEN_SECRET=          # để trống, app tự tạo lần chạy đầu

# Ảnh số qua QR (mục 11)
R2_ACCOUNT_ID=...
R2_BUCKET=...
R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
R2_PUBLIC_URL=https://pub-<hash>.r2.dev
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...

# Tự xác nhận chuyển khoản (mục 10, tuỳ chọn)
SEPAY_API_TOKEN=
```

Mật khẩu admin và PIN cũng đổi được ngay trong trang quản trị (mục 7). Sửa trực tiếp trong `.env` cũng có hiệu lực ngay, không cần khởi động lại.

### 6.4. Chạy lần đầu

Nhấp đúp **`run-local.bat`** trong thư mục dự án.

Lần đầu script tự tạo môi trường Python (`.venv`) và cài thư viện, mất vài phút và cần Internet. Xong nó mở trình duyệt tới `http://127.0.0.1:8000/`.

**Kiểm tra:**

- Thấy màn chờ "Cười lên. nhận ảnh ngay!".
- Mở `http://127.0.0.1:8000/admin` → đăng nhập bằng `ADMIN_PASSWORD` → thấy trang Tổng quan.

> Muốn tắt phần mềm: đóng cửa sổ dòng lệnh đen của `run-local.bat`.

---

## 7. Cấu hình trong trang quản trị

Mở `http://127.0.0.1:8000/admin`, vào **Cài đặt kiosk**. Mỗi lần sửa sẽ hiện thanh "Có N thay đổi chưa lưu"; bấm **Lưu thay đổi**.

| Mục | Việc cần làm |
|---|---|
| **Giá & thanh toán** | Giá gói 2/3/4 ảnh, giá mỗi lần chụp lại, số lần chụp lại tối đa |
| **Thời gian** | Đếm ngược mỗi kiểu, thời gian chờ thanh toán, tự in sau bao lâu, thời gian hiện QR |
| **Trải nghiệm khách** | Bật sẵn ảnh số qua QR, âm thanh, giảm hiệu ứng (máy yếu), dùng webcam khi camera chính lỗi, số ngày giữ ảnh trên cloud |
| **Hiệu ứng nền** | Bật/tắt từng hiệu ứng (vệt foil, viền holo, quầng sáng, hạt film, vệt sáng, chiều sâu màn chờ). Máy bị giật thì tắt **Hạt film** trước |
| **Chuyển khoản (VietQR)** | Chọn ngân hàng, số tài khoản, tên chủ tài khoản (mục 10) |
| **Mã giảm giá** | Tạo mã như `KHAI-TRUONG`, giảm theo đồng hoặc %, giới hạn lượt, hạn dùng |
| **In ảnh & khách quen** | Bật **Gửi lệnh in tới máy in** (sau khi xong mục 9), giá bản in thêm, số bản tối đa, tích điểm khách quen, hotline hiện khi máy in lỗi, trang mạng xã hội in trên ảnh story |
| **Bảo mật** | Đổi mật khẩu admin (≥ 6 ký tự) và PIN nhân viên (4 số). **Bắt buộc đổi** khỏi mặc định `0000` / `1234` |

**Kiểm tra:** về màn kiosk, chọn một gói → giá hiển thị đúng giá vừa đặt.

---

## 8. Camera

Kiosk chọn camera theo thứ tự:

1. **Camera thật đã cấu hình trên máy chủ** (máy ảnh qua digiCamControl, hoặc webcam cấu hình trong cấu hình nâng cao).
2. Nếu chưa có camera thật: **webcam của laptop/webcam USB qua trình duyệt** (tự động, không cần cấu hình).
3. Camera ảo (video mẫu) chỉ là phương án cuối để không kẹt phiên.

### 8.1. Dùng webcam (laptop hoặc webcam USB): cấu hình A và B

Không cần cấu hình gì: kiosk tự mở webcam khi tới màn chuẩn bị chụp.

- Lần đầu trình duyệt hỏi quyền camera → bấm **Allow** (cho phép). Ở chế độ kiosk (mục 13) quyền được cấp tự động.
- Có cả webcam laptop và webcam USB: Chrome dùng camera mặc định. Đổi tại `chrome://settings/content/camera`, chọn webcam USB.
- Trình duyệt chỉ cho mở camera khi vào bằng `http://127.0.0.1:8000` hoặc `http://localhost:8000`. **Không** mở kiosk bằng địa chỉ IP trong mạng LAN.

**Kiểm tra:** đi một phiên thử (nhân viên nhập PIN) → màn "Sẵn sàng chưa?" hiện hình từ webcam, có góc trên chữ "Camera thiết bị" khi chụp.

### 8.2. Dùng máy ảnh Canon/Nikon: cấu hình C

1. Cài **digiCamControl** (digicamcontrol.com) và xem danh sách máy được hỗ trợ trước khi mua máy.
2. Máy ảnh: cắm **pin giả**, tắt chế độ tự tắt nguồn (Auto power off), chế độ chụp **M** hoặc **P**, lấy nét **AF**, định dạng ảnh **JPEG** (không RAW), cỡ ảnh vừa (M) là đủ in 4×6.
3. Cắm USB vào laptop, mở digiCamControl → thấy tên máy ảnh → chụp thử một tấm trong digiCamControl.
4. Trong digiCamControl: **File → Settings → Webserver** → bật **Use web server**, cổng **5513** → khởi động lại digiCamControl.
5. Mở cấu hình nâng cao `http://127.0.0.1:8000/classic#/admin/config` → mục **Cameras** → thêm backend loại **Digicamcontrol** với *base_url* `http://127.0.0.1:5513`, đặt làm camera chụp (stills) và camera xem trước (video) → lưu → khởi động lại phần mềm.

**Kiểm tra:** `http://127.0.0.1:8000/api/framebooth/camera-status` trả về `"available": true, "virtual": false`.

> Mẹo ánh sáng cho máy ảnh: ISO 200–400, khẩu f/5.6–f/8 (nhóm đông vẫn nét), tốc 1/125 s, cân bằng trắng theo nhiệt màu đèn.

---

## 9. Máy in

Phần mềm in qua **một lệnh của Windows**. Cách dễ và miễn phí cho mục đích thương mại là dùng **SumatraPDF** (in được ảnh JPG, chỉnh vừa khổ).

### 9.1. Cài máy in

1. Tải driver đúng model từ trang hãng (Canon/DNP/Citizen), **cài driver trước rồi mới cắm USB**.
2. Lắp giấy và băng mực.
3. Windows: **Settings → Bluetooth & devices → Printers & scanners** → chọn máy in → **Printing preferences**:
   - Khổ giấy **4×6" (10×15 cm, Postcard)**.
   - **Borderless / Không viền** nếu máy hỗ trợ.
   - Hướng **Portrait (dọc)** cho khung dọc.
   - Máy DNP/Citizen in dải 2×6: bật chế độ **2‑inch cut** trong driver.
4. In thử một ảnh từ Windows Photos để chắc máy in chạy.

### 9.2. Nối phần mềm với máy in

1. Cài **SumatraPDF** (sumatrapdfreader.org) vào đường dẫn mặc định.
2. Mở cấu hình nâng cao `http://127.0.0.1:8000/classic#/admin/config` → mục **Share** → hành động đầu tiên (*actions[0]*):
   - **share_command**:
     ```
     "C:\Program Files\SumatraPDF\SumatraPDF.exe" -print-to "{printer_name}" -print-settings "fit" -silent "{filename}"
     ```
     (đổi đường dẫn nếu SumatraPDF cài chỗ khác, ví dụ `%LOCALAPPDATA%\SumatraPDF\SumatraPDF.exe`)
   - Lưu lại.
3. Trang `/admin` → **Máy in & camera** → chọn đúng máy in làm **máy in của kiosk** → bấm **In thử**.
4. Trang `/admin` → **Cài đặt** → **In ảnh & khách quen** → bật **Gửi lệnh in tới máy in** → Lưu.

**Kiểm tra:**

- "In thử" ra một trang có các ô màu.
- Đi một phiên thật, bấm **In ảnh** → ảnh ghép ra máy in.
- Rút giấy ra rồi in → kiosk hiện màn **"Máy in đang hết giấy"** với mã lỗi, khách có thể nhận ảnh số trước.

> Kích thước ảnh in = kích thước khung ảnh (mục 12). Khung 4×6" ở 300 dpi là **1200×1800 px** (dọc).

---

## 10. Thanh toán chuyển khoản tự động

Có hai cách, dùng song song được:

- **Nhân viên xác nhận bằng PIN** (mặc định): khách chuyển khoản hoặc trả tiền mặt, nhân viên kiểm tra rồi nhập PIN trên kiosk.
- **Tự xác nhận qua SePay**: tiền về tài khoản thì kiosk tự mở phiên chụp, không cần nhân viên đứng máy.

### 10.1. Hiện mã VietQR

`/admin` → **Cài đặt** → **Chuyển khoản (VietQR)**:

1. Chọn **ngân hàng**, nhập **số tài khoản** và **tên chủ tài khoản** (chữ in hoa không dấu).
2. Lưu.

**Kiểm tra:** màn thanh toán hiện mã QR. Quét bằng app ngân hàng → số tiền và nội dung chuyển khoản (dạng `TSLPB123456`) đã điền sẵn. **Đừng** chuyển thật lúc này.

### 10.2. Tự xác nhận qua SePay

1. Đăng ký **sepay.vn**, liên kết **đúng tài khoản ngân hàng** đã nhập ở 10.1.
2. Trong SePay: **Cấu hình công ty → API Access** → tạo **API Token**.
3. Dán vào `.env`: `SEPAY_API_TOKEN=token-vừa-tạo`.
4. Trang `/admin` → Cài đặt → thẻ VietQR hiện "Đã nối SePay (API token)".

Kiosk chỉ hỏi SePay **trong lúc có khách đang thanh toán** (mỗi 4 giây), không cần mở cổng mạng hay có địa chỉ công khai.

**Kiểm tra:** chuyển thử gói rẻ nhất bằng chính mã QR trên kiosk → trong vài giây kiosk hiện **"Thanh toán thành công!"**. Chuyển thiếu tiền → kiosk hiện **"Số tiền chưa đủ"** kèm QR cho phần còn thiếu.

> Khách chuyển khoản mà kiosk báo hết hạn mã: nhân viên kiểm tra app ngân hàng rồi nhập PIN. Mọi khoản chuyển đều được ghi lại.

---

## 11. Ảnh số qua QR (Cloudflare R2)

Bạn đã tạo bucket R2. Chi tiết từng bước có trong [cloudflare-r2-setup.md](cloudflare-r2-setup.md). Tóm tắt:

1. Điền 6 dòng `R2_...` trong `.env` (mục 6.3).
2. Bật **Public access** (r2.dev) cho bucket để khách mở được trang tải ảnh.
3. Khởi động lại phần mềm (đóng và mở lại `run-local.bat`).

Mỗi phiên, kiosk tải lên ảnh gốc, ảnh ghép, GIF boomerang, video timelapse và file ZIP, kèm một trang tải ảnh cho điện thoại. Trang đó có ảnh story/bài đăng dựng sẵn, clip 15 giây và nút "Xoá ảnh của tôi ngay". Ảnh tự xoá sau số ngày cài trong **Cài đặt → Giữ ảnh số trên cloud**.

**Kiểm tra:** `/admin` → **Máy in & camera** thấy "Cloudflare R2 · đã kết nối". Đi một phiên → quét QR bằng điện thoại **dùng 4G** (không dùng Wi‑Fi tiệm) → mở được trang ảnh.

---

## 12. Khung ảnh

`/admin` → **Khung ảnh** → tải lên file **PNG có vùng trong suốt** ở chỗ đặt ảnh. Phần mềm tự nhận diện các ô ảnh.

- Chọn số ô đúng gói: **2, 3 hoặc 4 ảnh**.
- Kích thước khuyến nghị: **1200×1800 px** (4×6" dọc, 300 dpi). Máy in dải 2×6: thiết kế 2 dải giống nhau đặt cạnh nhau trên khổ 4×6 để máy cắt đôi.
- Mỗi gói nên có 3–5 khung để khách chọn, thay khung theo mùa (Tết, Trung thu, Halloween, Noel…).

**Kiểm tra:** ở bước **Màu & viền** của kiosk thấy khung mới trong danh sách **Viền**.

---

## 13. Chế độ kiosk: tự bật khi mở máy, toàn màn hình

Mục tiêu: bật laptop là kiosk tự chạy toàn màn hình, khách không thoát ra được.

### 13.1. Tạo file khởi động

Tạo file `start-kiosk.bat` trong thư mục dự án với nội dung:

```bat
@echo off
cd /d D:\photobooth-app-tsl
start "photobooth" /min cmd /c run-local.bat -NoBrowser
timeout /t 25 /nobreak >nul
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --kiosk "http://127.0.0.1:8000/" ^
  --user-data-dir="%LOCALAPPDATA%\TSLKiosk" ^
  --autoplay-policy=no-user-gesture-required ^
  --use-fake-ui-for-media-stream ^
  --disable-pinch --overscroll-history-navigation=0 ^
  --noerrdialogs --disable-session-crashed-bubble --disable-features=Translate
```

Giải thích các tham số:

- `--kiosk`: toàn màn hình, không thanh địa chỉ.
- `--use-fake-ui-for-media-stream`: tự cho phép camera, không hiện hộp hỏi quyền.
- `--autoplay-policy=…`: cho phép âm thanh hiệu ứng ngay từ đầu.
- `--disable-pinch`, `--overscroll-history-navigation=0`: chặn khách phóng to hoặc vuốt quay lại trang trước.
- `--user-data-dir`: tách hồ sơ Chrome của kiosk khỏi Chrome thường.

Chỉnh đường dẫn `D:\photobooth-app-tsl` cho đúng. `-NoBrowser` để phần mềm không tự mở thêm một tab trình duyệt thường.

### 13.2. Tự chạy khi đăng nhập Windows

1. Nhấn `Win + R` → gõ `shell:startup` → Enter.
2. Tạo **shortcut** tới `start-kiosk.bat` trong thư mục vừa mở.
3. Đặt tài khoản kiosk **tự đăng nhập**: `Win + R` → `netplwiz` → bỏ tick *Users must enter a user name and password* (Windows 11 có thể phải tắt trước tuỳ chọn "Require Windows Hello sign-in").

### 13.3. Thoát chế độ kiosk khi cần

- Nhấn `Alt + F4` (cần bàn phím) để đóng Chrome kiosk.
- Hoặc `Ctrl + Alt + Del` → Task Manager → đóng Chrome.

**Kiểm tra:** khởi động lại laptop → khoảng 30–60 giây sau màn khách tự hiện màn chờ, toàn màn hình, chạm được.

---

## 14. Lắp đặt vật lý từng bước

Làm theo thứ tự để không phải tháo ra lắp lại.

1. **Chọn vị trí**: gần ổ điện, không có cửa kính hay đèn mạnh sau lưng khách, có chỗ xếp hàng.
2. **Dựng phông nền** và đánh dấu vạch "đứng tại đây" trên sàn, cách phông 0,5–1 m.
3. **Đặt chân màn hình** cách vạch đứng 1,5–2,5 m. Lắp màn cảm ứng sao cho **mép dưới màn cao ~1,0–1,1 m** (người lớn chạm thoải mái, trẻ em vẫn với được).
4. **Gắn camera** ngay trên mép trên màn, ống kính cao ~1,5–1,6 m, hướng thẳng vào khu khách đứng.
5. **Dựng hai đèn** chéo 45° hai bên camera, cao ~1,8–2 m, chĩa xuống nhẹ. Đặt độ sáng 50–70%, nhiệt màu ~5000–5600 K.
6. **Đặt bàn/kệ** cho laptop và máy in phía sau hoặc bên cạnh màn, máy in quay khay ra phía khách.
7. **Đấu nối** theo bảng mục 4.2; cắm laptop, màn và máy in vào **UPS**.
8. **Bó dây**: dây rút gom từng bó, dán băng keo vải các đoạn trên sàn.
9. **Bật máy**, chạy kiosk, căn khung hình: đứng vào vạch, xem màn chuẩn bị chụp. Đầu không bị cắt, nhóm 3–4 người vừa khung nét đứt.
10. **Chỉnh đèn** đến khi mặt sáng đều, không bóng gắt dưới cằm, không loá kính.
11. **Dán hướng dẫn nhỏ** cạnh màn: giá gói, "Chạm để bắt đầu", hotline.

---

## 15. Kiểm tra trước khi mở cửa

Làm hết danh sách này **trước ngày mở bán** và mỗi khi di chuyển máy.

- [ ] Đã đổi mật khẩu admin và PIN khỏi mặc định.
- [ ] Giá gói, giá chụp lại, giá bản in thêm đúng.
- [ ] Màn chờ hiện đủ, chạm được ở mọi góc màn.
- [ ] Phiên trả bằng **PIN**: chụp đủ kiểu → chọn ảnh → màu & khung → trang trí → **in ra giấy** → QR mở được trên điện thoại 4G.
- [ ] Phiên trả bằng **chuyển khoản thật** (gói rẻ nhất): kiosk tự xác nhận (nếu đã nối SePay).
- [ ] Mã giảm giá dùng được.
- [ ] Rút giấy giữa chừng → màn báo lỗi máy in → lắp lại giấy → "Chờ in lại" in được tiếp.
- [ ] Rút cáp mạng → vẫn chụp và in được (ảnh số dùng link nội bộ, khách không quét được từ xa: nên có 4G dự phòng).
- [ ] Rút điện tường → UPS giữ máy chạy, phiên đang dở vẫn in xong.
- [ ] Khởi động lại laptop → kiosk tự lên toàn màn hình.
- [ ] Trang `/admin` → Tổng quan hiện các phiên vừa thử; xoá/ghi chú các phiên thử để không lẫn doanh thu.
- [ ] Máy in còn ≥ 1 bộ giấy + mực dự phòng.

---

## 16. Vận hành hằng ngày

### Mở cửa

1. Bật UPS → bật laptop (kiosk tự chạy) → bật đèn.
2. Nhìn màn chờ: góc phải trên hiện **"Sẵn sàng"**.
3. `/admin` → **Máy in & camera**: máy in **Sẵn sàng**, camera OK, cloud OK.
4. Kiểm tra giấy và mực đủ cho cả ngày.

### Trong ca

- Nhân viên chỉ cần nhớ **PIN** để xác nhận khách trả tiền mặt hoặc khi chuyển khoản không tự xác nhận.
- Xem doanh thu và phiên ngay trên điện thoại:
  1. Cho laptop và điện thoại cùng Wi‑Fi.
  2. Chạy phần mềm với `--host 0.0.0.0` (sửa `HostName` trong `run-local.ps1`).
  3. Mở `http://<IP-laptop>:8000/admin` trên điện thoại.
  4. Màn khách trên laptop vẫn mở bằng `127.0.0.1` để camera hoạt động.
- In lại ảnh cho khách: `/admin` → **Phiên & doanh thu** → chọn phiên → **In lại**.

### Đóng cửa

1. `/admin` → Tổng quan: chốt doanh thu ngày; **Phiên & doanh thu** → tải **CSV** nếu cần đối soát.
2. Đối chiếu tổng tiền chuyển khoản với sao kê ngân hàng.
3. Tắt Chrome kiosk (`Alt + F4`) → tắt laptop đúng cách → tắt đèn → tắt UPS.
4. Đậy máy in để tránh bụi bám giấy.

---

## 17. Xử lý sự cố thường gặp

| Hiện tượng | Nguyên nhân hay gặp | Cách xử lý |
|---|---|---|
| Màn chuẩn bị chụp **không có hình** hoặc báo "Không mở được camera" | App khác đang giữ camera; Chrome chưa được cấp quyền; mở kiosk bằng IP thay vì 127.0.0.1 | Đóng Zoom/Teams/Camera; kiểm tra `chrome://settings/content/camera`; mở đúng `http://127.0.0.1:8000` |
| Hình camera là **video mẫu có người cầm ria mép** | Chưa có camera thật và webcam trình duyệt bị chặn | Cấp quyền camera cho Chrome (hoặc dùng cờ `--use-fake-ui-for-media-stream` ở mục 13) |
| Bấm in **không ra giấy**, không báo lỗi | Chưa bật "Gửi lệnh in tới máy in"; lệnh in vẫn là `echo` | Làm lại mục 9.2 |
| Kiosk báo **máy in hết giấy / kẹt giấy / mất kết nối** | Đúng như thông báo | Nạp giấy/mực, gỡ kẹt, cắm lại USB → khách bấm "Chờ in lại". Ảnh không mất; có thể in lại từ `/admin` |
| Khách đã chuyển khoản nhưng kiosk **không tự mở** | Chưa nối SePay; nội dung chuyển khoản bị khách sửa; mạng rớt | Nhân viên xem app ngân hàng → nhập PIN |
| QR ảnh số **không mở được** trên điện thoại | Chưa cấu hình R2 hoặc mất mạng lúc tải lên | Kiểm tra `.env` và Internet; mục 11 |
| Chạm màn khách mà con trỏ chạy **sang màn laptop** | Windows nhận sai màn cảm ứng | Tablet PC Settings → Setup (mục 4.3) |
| Giao diện **giật, chậm** | Laptop yếu | Cài đặt → tắt **Hạt film**, rồi các hiệu ứng nền khác; hoặc bật **Giảm hiệu ứng** |
| Quên **mật khẩu admin** | — | Mở `.env`, sửa `ADMIN_PASSWORD=...`, đăng nhập lại |
| Kiosk **không tự chạy** sau khi bật máy | Shortcut startup sai đường dẫn; Windows chưa tự đăng nhập | Kiểm tra mục 13.2 |

Nhật ký lỗi chi tiết nằm trong thư mục `log/` của dự án; gửi file mới nhất cho người hỗ trợ kỹ thuật khi cần.

---

## 18. Sao lưu và bảo mật

**Những gì cần sao lưu** (chép ra USB hoặc Google Drive mỗi tuần):

| Thư mục/file | Chứa |
|---|---|
| `.env` | Mật khẩu, PIN, khoá R2, SePay (**giữ bí mật**, không gửi qua chat công khai) |
| `config/` | Toàn bộ cài đặt (giá, khung, camera, lệnh in) |
| `database/` | Doanh thu, lịch sử phiên, nhật ký PIN, khách quen |
| `userdata/` | Khung ảnh đã tải lên |
| `media/` | Ảnh khách đã chụp (dung lượng lớn; xoá định kỳ theo chính sách giữ ảnh của tiệm) |

**Bảo mật:**

- Đổi mật khẩu admin và PIN khỏi mặc định; đổi PIN khi có nhân viên nghỉ việc.
- Không cho khách chạm vào laptop; tài khoản Windows của kiosk không có quyền admin.
- Không đưa `.env` lên Git, không chụp màn hình `.env` gửi người khác.
- Nếu lỡ lộ khoá R2/SePay: tạo khoá mới trên Cloudflare/SePay, thay trong `.env`, xoá khoá cũ.
- Ảnh khách là dữ liệu cá nhân: chỉ đăng lên trang của tiệm khi khách tick đồng ý trên màn QR (trang `/admin` ghi lại lựa chọn này cho từng phiên).

---

## 19. Lộ trình nâng cấp

| Giai đoạn | Việc làm | Mục tiêu |
|---|---|---|
| **Tuần 1–2** | Cấu hình A/B: laptop + màn cảm ứng + webcam + SELPHY + đèn; thanh toán bằng PIN | Chạy thật, đo số khách/ngày, nghe góp ý (màn cảm ơn có nút đánh giá) |
| **Tháng 1** | Nối SePay để tự xác nhận chuyển khoản; bật ảnh số qua QR; mã giảm giá khai trương | Giảm phụ thuộc nhân viên đứng máy |
| **Tháng 2–3** | Lên máy ảnh qua digiCamControl; thêm máy in dự phòng; vỏ kiosk | Ảnh đẹp hơn rõ rệt, máy gọn và bền |
| **Khi ≥ 30–40 phiên/ngày** | Máy in chuyên nghiệp (DNP/Citizen), cuộn giấy lớn | In nhanh, chi phí/tờ thấp, không phải thay giấy liên tục |
| **Mở thêm điểm** | Nhân bản: mỗi điểm một laptop + bộ thiết bị như trên, dùng chung bucket R2; doanh thu xem riêng ở `/admin` của từng máy | Mở rộng không cần máy chủ trung tâm |

---

*Tài liệu đi kèm:*

- [cloudflare-r2-setup.md](cloudflare-r2-setup.md): cài ảnh số qua QR chi tiết.
- [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md): tài liệu kỹ thuật của dự án.
