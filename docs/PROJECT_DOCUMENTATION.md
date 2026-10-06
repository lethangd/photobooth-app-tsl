# Tài liệu dự án — Photobooth App (TSL fork)

> Tài liệu này mô tả toàn bộ tính năng và luồng hoạt động hiện tại của source code trong repo này (nhánh `main`, tính đến commit `69e4521f`). Được viết dựa trên việc đọc trực tiếp code, không suy đoán.

## 0. Dự án này là gì

Repo là một **fork riêng (tên package vẫn giữ `photobooth-app`, thư mục `photobooth-app-tsl`)** của dự án mã nguồn mở [photobooth-app](https://photobooth-app.org) (Python + FastAPI, MIT license, tác giả gốc `mgineer85`). Phiên bản gốc: `v9.0.0`.

Người dùng/tác giả của fork này (`Lê Minh Thắng`) đã thêm một **chế độ kiosk tự phục vụ ("Framebooth")** dành riêng cho mô hình photobooth in ảnh tại điểm du lịch, nằm song song với ứng dụng gốc (gọi tắt trong tài liệu này là **"Classic"**). Ba commit gần nhất trên `main` đều là của fork:

| Commit | Nội dung |
|---|---|
| `080d05a1` | Khởi tạo route `/framebooth`, thêm khung ảnh, trang `framebooth.html` đầu tiên |
| `cb1cc3fe` | Auto-detect ô ảnh trong khung bằng OpenCV, thêm bộ lọc màu, viết đặc tả UX (`photobooth-kiosk-ux-spec.md`) |
| `69e4521f` | Thêm video timelapse (ghi từ live-view phía client + fallback dựng từ ảnh tĩnh), viết tài liệu Cloudflare R2 |

Vì vậy ứng dụng thực chất là **hai app dùng chung một backend**:

1. **Classic** — SPA Vue3 đã build sẵn (`src/web/frontend/index.html` + `assets/*.js`), đầy đủ tính năng gốc của photobooth-app (chụp ảnh/collage/animation/video/wigglegram, gallery, admin panel...).
2. **Framebooth (Kiosk TSL)** — một trang HTML+JS thuần (`src/web/frontend/framebooth.html`, ~2700 dòng, không build) mô phỏng một kiosk tự phục vụ bán ảnh in tại khu du lịch, hiện được gắn làm **trang mặc định `/`**.

```
GET /            → framebooth.html   (kiosk TSL, MẶC ĐỊNH)
GET /classic     → index.html        (SPA gốc photobooth-app)
```

Định nghĩa tại [src/photobooth/routers/static.py](../src/photobooth/routers/static.py).

---

## 0.1 Trạng thái sau đợt refactor (2026-09)

Sau khi tài liệu này được viết lần đầu, repo đã trải qua một đợt refactor để **tập trung hẳn vào luồng kiosk Framebooth + admin**, loại bỏ các phần của photobooth-app gốc không phục vụ mục tiêu đó. Kế hoạch: `C:\Users\Admin\.claude\plans\twinkling-percolating-perlis.md`.

**Đã thay đổi so với nội dung mô tả bên dưới:**

| Vùng | Trước | Sau refactor |
|---|---|---|
| Tham số kiosk (giá, buffer, countdown, timeout, filters) | Hằng số hard-code trong `routers/api/framebooth.py` | Nhóm config `appconfig.framebooth` ([services/config/groups/framebooth.py](../src/photobooth/services/config/groups/framebooth.py)), sửa được qua **Admin → Config** (form tự sinh từ JSON Schema) |
| Code kiosk | 1 file router ~480 dòng (HTTP + business + xử lý ảnh) | Router mỏng + service layer [services/framebooth/](../src/photobooth/services/framebooth/) (`templates`, `filters`, `renderer`, `timelapse`, `session_store`) + có test (`test_framebooth.py`) |
| Loại action | image, collage, **animation, video, multicamera** | **Chỉ image + collage** (`ActionType`), phần animation/video/wigglegram + processing/steps đã xoá |
| Camera backend | Virtual, Gphoto2, Digicamcontrol, **Picamera2, WebcamV4l, WebcamPyav, Wigglecam** | **Chỉ Virtual + Gphoto2 (Linux/Mac) + Digicamcontrol (Windows)** |
| Plugin | commander, gpio_lights, wled, synchronizer, filter_pilgram2 | **Chỉ filter_pilgram2** |
| GPIO / bàn phím | `GpioService` + nhóm config `hardwareinputoutput` | **Đã xoá hoàn toàn** (kiosk là màn cảm ứng) |
| Admin | + `/api/admin/multicamera/*` (hiệu chỉnh đa camera) | Đã xoá router multicamera + `utils/multistereo_calibration` |
| Dependency | + `gpiozero`, `linuxpy`, `wigglecam`, `pynng`, `rclone-bin-api` | Đã gỡ khỏi `pyproject.toml` |
| SPA "Classic" | — | **Giữ nguyên bundle** (không có source Vue để sửa) — chỉ dùng phần Admin (Config/Files/Logs/Dashboard); các trang khách cũ (chụp ảnh/gallery) vẫn chạy nhờ action `image`/`collage` được giữ, nhưng không còn là trọng tâm |

Các mục **thanh toán VietQR, máy in nhiệt, upload Cloudflare R2** vẫn là **mock** (đợt refactor này chỉ tái cấu trúc + đưa tham số vào config, không tích hợp phần cứng/dịch vụ thật).

Các mục 2, 3.1, 6, 7, 9.2 bên dưới mô tả trạng thái **trước** refactor — đọc kèm bảng trên.

---

## 1. Kiến trúc tổng thể

```
┌──────────────────────────────────────────────────────────────────┐
│                         FastAPI app (uvicorn)                     │
│  src/photobooth/application.py → app = FastAPI(...)               │
│                                                                     │
│  Routers:                                                          │
│   /api/...            (api router - public/kiosk dùng)            │
│   /api/admin/...      (api_admin router - cần JWT bearer)         │
│   /media/{dim}/{id}   (media_router - ảnh/video đã cache)         │
│   /userdata/...       (userdata_router - file người dùng tự thêm) │
│   /  , /classic       (static_router - HTML SPA / kiosk)          │
│   /sharepage/         (StaticFiles - trang share-on-demand)       │
│   /  (fallback)       (StaticFiles - toàn bộ SPA build sẵn)       │
└───────────────────────────┬─────────────────────────────────────┘
                             │ dùng chung singleton
                             ▼
                    container = Container()   (src/photobooth/container.py)
     ┌───────────────────────────────────────────────────────────┐
     │ logging_service, pluginmanager_service, acquisition_service,│
     │ mediacollection_service, information_service,               │
     │ processing_service, system_service, share_service,          │
     │ gpio_service, config_service                                │
     └───────────────────────────────────────────────────────────┘
```

`container` là **singleton toàn cục** (class attribute, không phải DI framework). `container.start()`/`stop()`/`reload()` khởi động/tắt lần lượt các service theo đúng thứ tự khai báo (và thứ tự ngược lại khi tắt). `reload()` được gọi khi admin lưu cấu hình hoặc gọi `GET /api/system/service/reload`.

### Khởi động ứng dụng

`src/photobooth/__main__.py`:
1. `create_db_and_tables()` — tạo DB SQLite + chạy alembic nếu cần, trước khi mọi thứ khác chạy.
2. Tạo `uvicorn.Server` (mặc định `host=0.0.0.0`, `port=8000`).
3. `container.start()` rồi `server.run()` (blocking, vòng lặp vô hạn).
4. `Ctrl+C`/`SIGTERM` → `application.py: lifespan()` bắt signal, gọi `container.stop()` sạch sẽ.

Trên Windows, repo có thêm 2 file tiện ích **không thuộc code gốc**: [run-local.ps1](../run-local.ps1) và [run-local.bat](../run-local.bat) — tự tạo `.venv`, `pip install -e .`, chạy `python -m photobooth --host 127.0.0.1 --port 8000` và mở trình duyệt. Dùng cho dev nhanh trên máy Windows, không phải một phần chính thức của app.

### Thư mục dữ liệu runtime (tạo tự động cạnh working directory)

Định nghĩa ở [src/photobooth/appconfig.py](../src/photobooth/appconfig.py):

| Thư mục | Vai trò |
|---|---|
| `./database/` | file SQLite (`database.db`) |
| `./cache/` | các phiên bản resize (full/preview/thumbnail) của media, cache bust theo `revision` |
| `./media/camera_original/` | ảnh gốc y hệt lúc chụp từ camera |
| `./media/processed_full/` | ảnh/video đã qua pipeline xử lý (là ảnh hiển thị trong gallery) |
| `./userdata/` | file người dùng tự thêm (font, ảnh nền, khung overlay, `private.css`...) |
| `./userdata/demoassets/` | **symlink/junction** trỏ vào `src/photobooth/demoassets/userdata` (ảnh mẫu đi kèm app) |
| `./log/` | log file |
| `./config/` | `config.json` (cấu hình app), `rclone.conf` (nếu dùng plugin synchronizer) |
| `./tmp/` | file tạm (ảnh đang chờ duyệt, `tmp/framebooth/*` của kiosk...) |
| `./recycle/` | "thùng rác" khi xoá media (nếu bật `users_delete_to_recycle_dir`) |

---

## 2. Camera & thu nhận ảnh (Acquisition)

`AcquisitionService` ([src/photobooth/services/acquisition.py](../src/photobooth/services/acquisition.py)) quản lý **tối đa nhiều backend camera cùng lúc**. Mỗi backend cấu hình trong `appconfig.cameras.group_backends` (danh sách, mỗi phần tử có `enabled` + `backend_config` phân biệt theo `backend_type`).

Có 3 "vai trò" độc lập, có thể trỏ tới 3 backend khác nhau (config `index_backend_stills` / `index_backend_video` / `index_backend_multicam`):
- **stills**: chụp ảnh chất lượng cao (VD: DSLR qua gphoto2, trong khi webcam rẻ tiền lo live-view).
- **video**: cấp live-view (MJPEG) + quay video/boomerang.
- **multicam**: chụp đồng bộ nhiều camera cho wigglegram (3D).

### Danh sách backend hỗ trợ (theo OS, xem `services/config/groups/cameras.py`)

| Backend | Nền tảng | Ghi chú |
|---|---|---|
| `VirtualCamera` | mọi OS | camera giả lập bằng video demo (`demovideo.mp4`) — **mặc định của mọi cài đặt mới**, dùng để demo/test không cần phần cứng |
| `WebcamPyav` | mọi OS | webcam UVC qua PyAV/ffmpeg, chọn theo tên thiết bị |
| `Wigglecam` | mọi OS | nhiều node camera Raspberry Pi qua mạng (giao thức riêng `pynng`), dùng cho ảnh wigglegram nhiều góc |
| `Picamera2` | Linux | camera CSI của Raspberry Pi |
| `WebcamV4l` | Linux | webcam qua V4L2 trực tiếp |
| `Gphoto2` | Linux/Mac | DSLR/mirrorless tethered qua libgphoto2 |
| `Digicamcontrol` | Windows | điều khiển DSLR qua phần mềm digiCamControl (HTTP) |

Mỗi backend implement `AbstractBackend` ([services/backends/abstractbackend.py](../src/photobooth/services/backends/abstractbackend.py)): có state machine nội bộ (`still`/`video`/`standby`), hàng đợi request ảnh (`StillRequest`, `MulticamRequest`), broadcast khung hình lores cho live-view (`LoresBroadcastRes`), tính FPS, tự xoay ảnh theo EXIF orientation.

**Live-view** cấp qua 2 cách: WebSocket `GET /api/aquisition/stream` (gửi khung theo nhịp "ready" từ client) và HTTP MJPEG `GET /api/aquisition/stream.mjpg` (multipart, đơn giản hơn — kiosk Framebooth dùng cách này qua `<img src="/api/aquisition/stream.mjpg">`).

**Video**: `SoftwareVideoRecorder` ghi video từ backend "video" (dùng cho action `video`/boomerang).

Mọi thao tác chụp đều gọi hook plugin trước/sau (`acq_before_shot`, `acq_after_shot`, `acq_thrill*`) để các plugin như WLED/GPIO đèn có thể phản ứng (nháy đèn đếm ngược, đổi màu khi chụp...).

---

## 3. Action & tiến trình chụp (Processing / State machine)

Đây là lõi nghiệp vụ của app gốc — dùng cho cả 2 UI (Classic lẫn Framebooth chỉ dùng phần capture đơn giản).

### 3.1 5 loại action

Cấu hình tại `appconfig.actions` ([services/config/groups/actions.py](../src/photobooth/services/config/groups/actions.py)), mỗi loại là **danh sách nhiều cấu hình** (để có nhiều nút "Ảnh 2 khung", "Ảnh 4 khung"... khác nhau), mỗi cấu hình gồm `jobcontrol` (đếm ngược, có cần duyệt ảnh không) + `processing` (pipeline xử lý) + `trigger` (nút UI/phím tắt/chân GPIO):

| Action | Job model | Mô tả |
|---|---|---|
| `image` | `JobModelImage` | 1 ảnh đơn: xoá nền AI, ghép nền, filter, khung overlay, chèn text |
| `collage` | `JobModelCollage` | N ảnh ghép vào 1 khung (mặc định có sẵn 3 mẫu: khung 2/3/4 ảnh — chính là nguồn gốc thư mục `frame/2,3,4` mà Framebooth tái sử dụng) |
| `animation` | `JobModelAnimation` | Ảnh động (GIF/WebP/AVIF/MP4) ghép nhiều khung hình + có thể áp filter pilgram2 khác nhau từng khung |
| `video` | `JobModelVideo` | Quay video, tuỳ chọn tạo boomerang (video tua ngược nối tiếp) |
| `multicamera` | `JobModelMulticamera` | Chụp đồng bộ nhiều camera → dựng "wigglegram" (ảnh 3D lắc qua lại) |

### 3.2 State machine (`ProcessingMachine`, [services/processor/machine/processingmachine.py](../src/photobooth/services/processor/machine/processingmachine.py))

```
start ──next──> counting ──next──> capture ──(cần duyệt?)──> approval
                   ▲                  │                         │
                   └──(chưa đủ ảnh)───┴─────────────────────────┘
                                       │ (đủ ảnh)
                                       ▼
                                  completed ──next──> present ──next──> finished
(abort: từ bất kỳ state nào → finished ngay)
```
- `next`: sự kiện tiến tới (đếm ngược xong, ảnh vừa chụp được duyệt tự động/thủ công...).
- `reject`: từ `approval` quay lại `counting` để chụp lại tấm đó (dùng cho collage khi bật `ask_approval_each_capture`).
- `abort`: huỷ toàn bộ job (dọn file tạm), nhảy thẳng `finished`.

`ProcessingService` ([services/processing.py](../src/photobooth/services/processing.py)) chạy state machine trong **1 thread riêng** (`_process_fun`), phát sự kiện `SseEventProcessStateinfo` qua SSE mỗi lần đổi state để UI cập nhật đếm ngược/ảnh preview realtime. Chỉ **1 job chạy tại một thời điểm** (`is_occupied()` → 400 nếu bấm trigger khi đang chạy).

Khi cần người dùng xác nhận (approval, hoặc video muốn dừng sớm), service dùng `Queue(maxsize=1)` để chờ input từ `POST /api/processing/{next|confirm|reject|abort}` (hoặc GPIO) trong khoảng `approve_autoconfirm_timeout` giây, hết giờ thì **tự động coi như "next"**.

Có 3 listener gắn vào mọi transition:
- `FrontendNotifierEventHooks` — bắn SSE cho UI.
- `PluginEventHooks` — gọi hook `sm_*` cho plugin (WLED đổi màu đèn theo state, commander gọi lệnh ngoài...).
- `DbListenter` — khi vào state `completed`, lưu các `Mediaitem` kết quả vào DB.

### 3.3 Pipeline xử lý ảnh (mediaprocessing)

`services/mediaprocessing/pipeline.py` implement một pipeline generic kiểu **chain-of-responsibility** (`PipelineStep` + `next_step`). `services/mediaprocessing/processes.py` lắp ráp pipeline theo config:

**Phase 1 — xử lý từng ảnh chụp riêng lẻ** (`process_image_inner`), theo thứ tự nếu bật:
1. `RemovebgStep` — xoá nền bằng AI (rembg, model `modnet`/`u2netp`/`u2net`, ONNX runtime)
2. `ImageMountStep` — ghép ảnh nền tuỳ chỉnh (file ảnh)
3. `FillBackgroundStep` — tô nền màu đặc
4. `PluginFilterStep` — áp filter (do plugin cung cấp, mặc định có bộ `filter_pilgram2`)
5. `ImageFrameStep` — dán khung overlay (PNG trong suốt) lên ảnh
6. `TextStep` — chèn text tuỳ biến (hỗ trợ `{date}`, `{time}`)

**Phase 2 — theo loại media**:
- Collage: `AddPredefinedImagesStep` + `PostPredefinedImagesStep` (chèn ảnh có sẵn không cần chụp) → `MergeCollageStep` (ghép các ảnh vào toạ độ đã định nghĩa) → rồi lại chạy một lượt phase-1-steps lên toàn bộ canvas (nền/khung/text cấp collage).
- Animation: căn chỉnh kích thước (`AlignSizesStep`) rồi encode thành GIF/WebP/AVIF/MP4 nhiều khung hình.
- Video: `BoomerangStep` (tạo hiệu ứng tua ngược, dùng PyAV, không còn phụ thuộc ffmpeg CLI — xem commit "remove outdated ffmpeg boomerang step").
- Multicamera: `AlignAsPerCalibrationStep` (căn ảnh theo hiệu chỉnh camera) rồi ghép chuỗi ảnh `1-2-3-4-3-2-lặp lại` thành wigglegram.

Ảnh kết quả cuối cùng luôn được `encode()` (`utils/media_encode.py`) ra `Mediaitem.processed`, lưu DB qua `MediacollectionService`.

---

## 4. Media Collection (thư viện ảnh / gallery)

`MediacollectionService` ([services/collection.py](../src/photobooth/services/collection.py)) là lớp nghiệp vụ trên 3 thành phần con (`services/mediacollection/`):
- `Database` — CRUD bảng `mediaitems` (SQLAlchemy).
- `Files` — kiểm tra/tồn tại file vật lý tương ứng, xoá (vào `recycle/` hoặc xoá hẳn).
- `Cache` — sinh & lưu các bản resize (`full`/`preview`/`thumbnail` — 3 `DimensionTypes`), cache-bust bằng cột `revision` (tăng tự động mỗi lần `Mediaitem` được update, xem `database/models.py`).

Model DB `Mediaitem`: `id (UUID)`, `media_type` (image/collage/animation/video/multicamera), `job_identifier`, `captured_original` (ảnh gốc, có thể null với collage/animation), `processed` (ảnh kết quả), `pipeline_config` (JSON — chính config Pydantic lúc xử lý, cho phép re-render khi đổi filter), `show_in_gallery`, `revision`, `created_at`.

Mỗi khi thêm/sửa/xoá item, service bắn **SSE** (`SseEventDbInsert/Update/Remove`) để mọi client (gallery đang mở) cập nhật realtime, đồng thời gọi hook `collection_files_added/updated/deleted` để plugin đồng bộ cloud (`synchronizer`) biết mà upload/xoá theo.

API công khai: `GET/DELETE /api/mediacollection`, `GET /media/{dimension}/{id}` (ảnh thật, có cache-control 1 ngày), `GET/PATCH /api/filter/{id}?filter=...` (đổi & preview filter ngay trên ảnh đã chụp mà không cần chụp lại).

---

## 5. Share / In ấn

`ShareService` ([services/share.py](../src/photobooth/services/share.py)) thực thi **một lệnh shell tuỳ ý** (`share_command`, mặc định chỉ `echo ...` — nghĩa là **không in thật ra giấy trừ khi admin tự cấu hình lệnh in**, ví dụ gọi tới CUPS/lệnh in Windows). Placeholder thay vào lệnh: `{filename}`, `{printer_name}`, `{media_type}`, `{action_config_name}` + tham số tuỳ biến (`{copies}`, `{mail}`...).

Có 3 action mẫu dựng sẵn: "Printing" (in trực tiếp), "Printing copies" (hỏi số bản in), "Mailing action" (gửi mail — cũng chỉ là mẫu `echo`).

Cơ chế bảo vệ:
- `max_shares` — giới hạn số lần share/in cho một action (đếm trong bảng `sharelimits`).
- `share_blocked_time` — chặn spam, phải cách nhau X giây giữa 2 lần in.
- `check_if_printer_is_idle` — kiểm tra máy in rảnh trước khi in (`utils/printer.py`).

---

## 6. Hệ thống Plugin

`src/photobooth/plugins/__init__.py` dùng thư viện **pluggy** (giống pytest). Plugin nạp từ 2 nguồn:
1. Entry point `photobooth11` khai báo trong `pyproject.toml` (5 plugin đóng gói sẵn).
2. Thư mục `./plugins/` cạnh working directory — cho phép người dùng tự viết plugin, chỉ cần đặt đúng tên class.

5 plugin đi kèm:

| Plugin | Chức năng |
|---|---|
| `commander` | Chạy lệnh shell hoặc gọi HTTP request khi có sự kiện (state machine, capture...) — dùng để tích hợp phần cứng/loa/relay ngoài |
| `gpio_lights` | Bật/tắt đèn LED thường qua GPIO theo trạng thái tiến trình |
| `wled` | Điều khiển dải LED WLED qua UART, đổi preset màu theo state (`STANDBY/THRILL/SHOOT/RECORD`, kể cả preset riêng cho từng loại capture still/video/multicam) |
| `filter_pilgram2` | Bộ lọc màu kiểu Instagram (thư viện `pilgram2`), là nguồn filter mặc định hiển thị trong Classic UI |
| `synchronizer` | Đồng bộ media lên cloud qua **rclone** (nhiều remote cùng lúc), có 2 chế độ: đồng bộ ngay khi có ảnh mới (`ThreadedImmediateSyncPipeline`) và đồng bộ định kỳ toàn bộ thư mục (`ThreadedRegularSync`, có theo dõi cắm USB), kèm `ShareOnDemandService` (sinh trang chia sẻ tĩnh) |

Các hook chính: `init/start/stop/get_stats` (vòng đời), `sm_*` (theo dõi transition của state machine), `acq_*` (trước/sau khi chụp), `mp_filter_pipeline_step`/`mp_avail_filter` (đăng ký bộ lọc ảnh mới), `collection_files_added/updated/deleted`, `get_share_links` (sinh link chia sẻ, ví dụ dùng bởi gallery để tạo QR).

---

## 7. Phần cứng & Input (GPIO / Keyboard)

`GpioService` ([services/gpio.py](../src/photobooth/services/gpio.py), dùng `gpiozero`, chỉ thật sự hoạt động trên Raspberry Pi — nếu không có driver phù hợp sẽ log cảnh báo và bỏ qua êm):
- Giữ chân GPIO 2 giây → `poweroff`/`reboot` máy.
- Mỗi action (image/collage/.../share) có thể gán 1 chân GPIO + kiểu trigger (`pressed`/`released`/`longpress`) để bấm nút vật lý.
- 3 chân riêng để **next/reject/abort** tiến trình đang chạy (dùng khi có nút bấm vật lý thay UI).

Bàn phím: nếu bật `keyboard_input_enabled`, mỗi action còn có `keyboard_input` (keycode) nhận từ sự kiện `keyup` trên trình duyệt (front-end tự bắt và gọi API tương ứng — không xử lý ở backend).

---

## 8. Realtime: Server-Sent Events (SSE)

Một endpoint duy nhất `GET /api/sse` ([routers/api/sse.py](../src/photobooth/routers/api/sse.py)) — mỗi client giữ 1 kết nối SSE, ping mỗi giây để giữ kết nối. Các loại sự kiện (`services/sse/sse_.py`):

| Sự kiện | Khi nào bắn |
|---|---|
| `SseEventProcessStateinfo` | mỗi lần state machine chuyển trạng thái (đếm ngược, đang chụp, đã xong...) |
| `SseEventDbInsert/Update/Remove` | thư viện ảnh có ảnh mới/sửa/xoá |
| `SseEventTranslateableFrontendNotification` | thông báo lỗi/cảnh báo có key i18n (ví dụ `processing.job_failed`, `share.quota_exceeded`) để UI tự dịch |
| `SseEventLogRecord` | stream log realtime cho trang Admin → Logs |
| `SseEventOnetimeInformationRecord` | thông tin hệ thống 1 lần khi vừa connect (version, OS, model máy, ổ đĩa...) |
| `SseEventIntervalInformationRecord` | mỗi 2 giây: CPU%, RAM, nhiệt độ, dung lượng đĩa, số ảnh trong DB/cache, thống kê camera, pin, cờ throttle của Pi, thống kê plugin |

Lưu ý: **Framebooth (kiosk) hiện KHÔNG dùng SSE** — toàn bộ luồng của nó chạy bằng `setTimeout`/`fetch` phía client, tự lập lịch (mock timers), không nhận realtime event từ backend.

---

## 9. Cấu hình & Admin Panel

### 9.1 Hệ thống cấu hình

`AppConfig` (pydantic-settings) gồm 8 nhóm (`services/config/groups/*.py`), lưu tại `config/config.json`, có thể override qua biến môi trường/`.env`:

| Nhóm | Nội dung chính |
|---|---|
| `common` | mật khẩu admin (mặc định `0000`), mức log, có chuyển vào recycle bin khi xoá không |
| `actions` | 5 loại action đã nói ở mục 3.1 |
| `share` | các action share/in |
| `mediaprocessing` | kích thước ảnh full/preview/thumbnail, bitrate video, model xoá nền, định dạng animation/wigglegram |
| `uisettings` | màu chủ đạo, theme sáng/tối, text trang chủ, timeout idle/slideshow, hiệu ứng mirror/blur live-view, cấu hình gallery (QR, nút tải/xoá/in) |
| `cameras` | danh sách backend camera (mục 2) |
| `hardwareinputoutput` | GPIO + bàn phím (mục 7) |
| `misc` | secret ký JWT, lệnh shutdown/reboot |

Mỗi model Pydantic tự sinh **JSON Schema** (`get_schema()`) để trang Admin Classic tự vẽ form cấu hình (không cần code frontend riêng cho từng field) — cơ chế qua `services/config/baseconfig.py` + `pydantic_extra_types` (Color...) + `json_schema_extra` tuỳ biến UI (slider, đánh dấu "tốn tài nguyên", API gợi ý danh sách file...).

Plugin cũng có thể có config riêng (VD `WledConfig`, `SynchronizerConfig`) — quản lý qua cùng cơ chế (`configurable` = tên plugin).

### 9.2 API Admin (`/api/admin/*`, yêu cầu JWT Bearer)

Đăng nhập: `POST /api/admin/auth/token` (OAuth2 password flow, username cố định do `admin_password` cấu hình) → JWT ký bằng `misc.secret`, hết hạn theo `ACCESS_TOKEN_EXPIRE_MINUTES`. `GET /api/admin/auth/me` kiểm tra token.

| Router | Endpoint chính |
|---|---|
| `config` | `GET /list` (liệt kê configurable = app + plugin), `GET/PATCH/DELETE /{configurable}`, `GET /{configurable}/schema` |
| `files` | trình quản lý file trong `userdata/`: liệt kê, xem, upload, tạo thư mục, xoá, nén ZIP tải về, dọn recycle bin |
| `enumerate` | liệt kê cổng serial, webcam USB, file người dùng (autocomplete cho form config), remote rclone |
| `information` | reset bộ đếm usage-stats |
| `multicamera` | hiệu chỉnh (calibration) nhiều camera cho wigglegram, sinh bảng Charuco, xem/xoá kết quả hiệu chỉnh |
| `share` | reset bộ đếm giới hạn share/in |

### 9.3 API công khai khác đáng chú ý

- `GET /api/system/host/{reboot|shutdown}`, `GET /api/system/service/reload` (áp dụng lại toàn bộ config = `container.reload()`), `GET /api/system/systemctl/{restart|stop|start|install|uninstall}` (cài đặt như systemd service trên Linux, `services/system.py`).
- `GET /api/debug/log/latest`.
- `GET /api/actions/{image|collage|animation|video|multicamera}/{index}` — trigger action, dùng bởi cả nút bấm UI Classic lẫn phím tắt/GPIO.
- `GET /api/processing/{next|confirm|reject|abort}`, `GET /api/processing/approval/{capture_id}` (ảnh preview khi đang chờ duyệt).

---

## 10. Frontend "Classic" (SPA Vue3 — bản build sẵn)

Nằm ở `src/web/frontend/` — **đã build**, không có source `.vue` trong repo này (chỉ bundle `assets/*.js/css`). Các trang xác định qua tên file build: `IndexPage` (trang chủ có nút trigger action + live-view), `GalleryPage`/`GalleryDetailPage` (thư viện ảnh, xem chi tiết, filter, share/in, xoá, QR tải), `SlideshowPage` (chiếu ảnh tự động khi rảnh), `LoginPage`/`AuthLayout`, `Admin1stStartPage`, `AdminDashboardPage`, `AdminConfigPage`, `AdminFilesPage`, `AdminLogsPage`, `AdminMulticamPage`, `AdminHelpPage`, `ErrorNotFound`.

Đây chính là UI **đầy đủ tính năng gốc** của photobooth-app (đa ngôn ngữ qua Crowdin/`vue-i18n`, dùng bộ UI Quasar `Q*`). Truy cập qua `/classic`.

Ngoài ra còn `src/web/sharepage/index.html` và `src/web/shareondemand/` (`api.php` + cấu hình nginx) — trang tĩnh để host trên máy chủ chia sẻ riêng (ví dụ khi bật hotspot cục bộ, khách quét QR vào thẳng trang share mà không cần chạy toàn bộ SPA).

---

## 11. Frontend "Framebooth" — Kiosk tự phục vụ (tính năng riêng của fork TSL)

Đây là phần **được phát triển thêm, không thuộc upstream**, và là trọng tâm các thay đổi gần đây. Gồm 2 phần: `routers/api/framebooth.py` (backend) + `web/frontend/framebooth.html` (toàn bộ UI+logic trong 1 file, vanilla JS, không phụ thuộc build tool).

### 11.1 Mục tiêu (theo đặc tả `src/photobooth/photobooth-kiosk-ux-spec.md`, viết tiếng Việt)

Một kiosk **hoàn toàn không người trông coi**, đặt tại điểm du lịch, khách tự: chọn gói (2/3/4 ảnh) → thanh toán VietQR → chụp tự động → chọn ảnh ưng ý → chọn filter → xem trước & xác nhận → in → quét QR nhận file gốc + video timelapse → cảm ơn. Ba nguyên tắc thiết kế xuyên suốt của đặc tả: **fail-safe** (khách trả tiền thì không được mất ảnh), **fail-forward** (mọi lỗi tự thoát về màn chờ, không "treo máy"), **recoverable session** (lưu tiến trình để phục hồi khi crash). File đặc tả còn mô tả chi tiết 12 màn hình (S1–S12), ma trận lỗi/timeout, bảng tham số admin, và 3 ý tưởng mở rộng (Photo Battle bình chọn ảnh, xuất bản mạng xã hội tự động, "Digital Passport" hành trình đa điểm) — **đây là bản thiết kế mục tiêu, chưa triển khai hết**, xem mục 11.5 phần khác biệt.

### 11.2 Luồng màn hình hiện có trong code (`framebooth.html`)

State machine phía **client** (biến JS `screens`, hàm `go(nextScreen)`), 12 trạng thái đúng như đặc tả:

```
IDLE → PACKAGE_SELECT → PAYMENT → GET_READY → CAPTURING → PHOTO_SELECT
  → FILTER_SELECT → (FRAME_SELECT*) → FINAL_PREVIEW → PRINTING → QR_DOWNLOAD → THANK_YOU → IDLE
```
`*FRAME_SELECT` có màn hình HTML riêng (`renderFrameChoices`) nhưng **hàm điều hướng `showFrameSelect()` hiện chỉ gọi lại `showFilterSelect()`** — nghĩa là bước chọn khung/frame theme độc lập đã được **gộp vào bước chọn filter** (mỗi gói layout N-ảnh chỉ tự map với khung mẫu đầu tiên có sẵn (`state.selectedTemplateId = cfg.templates[0].id`), người dùng không thao tác chọn khung riêng ở luồng chính nữa; code render khung cũ vẫn còn nhưng không được gọi từ luồng).

Chi tiết từng bước và timeout:

| Bước | Việc chính | Timeout / tự động |
|---|---|---|
| **IDLE** | Hiện 3 ảnh mẫu (hero strip) lấy từ khung có sẵn, nút "Chạm để bắt đầu" | chạm bất kỳ đâu trên màn hình cũng vào `PACKAGE_SELECT` |
| **PACKAGE_SELECT** | Toggle "Nhận file số & video timelapse" (bật/tắt), chọn 1 trong 3 gói 2/3/4 ảnh (giá + số lần chụp lấy từ `/api/framebooth/config`) | 60s không thao tác → reset về IDLE |
| **PAYMENT** | Vẽ QR **giả lập** (canvas tự vẽ pattern giống QR, KHÔNG phải QR thật/VietQR thật), thanh meter chạy trong `payment_mock_seconds` (2s) rồi tự coi là thanh toán thành công | không có timeout thật — luôn tự pass sau 2s (đây là **mock**, chưa có cổng thanh toán thật) |
| **GET_READY** | Hiện live-view camera thật (`/api/aquisition/stream.mjpg`), đếm `get_ready_seconds` (3s), có nút "Bắt đầu ngay" để bỏ qua chờ | tự chuyển sau 3s |
| **CAPTURING** | Với mỗi trong N+2 lần chụp: đếm ngược `countdown_seconds` (10s) → hiệu ứng flash trắng → gọi thật `POST /api/framebooth/capture` (chụp từ camera thật qua `acquisition_service`, retry tối đa 2 lần) → hiển thị thumbnail. Đồng thời **ghi video timelapse ngay từ live-view** bằng `MediaRecorder` + canvas (client-side, xem 11.3) nếu bật "file số" | lỗi camera sau khi retry → hiện overlay lỗi có nút "Thử lại"/"Về màn chờ" |
| **PHOTO_SELECT** | Lưới toàn bộ N+2 ảnh vừa chụp, chạm để chọn đúng N ảnh (badge số thứ tự), nút "Tiếp tục" chỉ bật khi đủ N | 45s cảnh báo, +15s nữa auto-chọn N ảnh đầu tiên theo thứ tự chụp rồi tự tiếp tục |
| **FILTER_SELECT** | Chọn 1 trong 5 filter (Natural/Vivid/Warm/B&W/Film), xem preview ghép khung thời gian thực (`composite-preview`, server render bằng PIL) | 45s cảnh báo, +10s auto dùng filter/khung hiện tại rồi sang `FINAL_PREVIEW` |
| **FINAL_PREVIEW** | Hiện ảnh ghép cuối full-size, panel video timelapse (đang dựng), nút "In ngay" gọi `POST /api/framebooth/render` (render thật + lưu vào DB gallery), QR tải trọn bộ (giả lập) | 30s không bấm "In ngay" → tự động in luôn |
| **PRINTING** | Animation ảnh trượt ra khỏi khe in (thuần CSS), thanh meter `printing_mock_seconds` (3s) | không có máy in thật — **mock hoàn toàn** |
| **QR_DOWNLOAD** | QR (giả lập) trỏ tới `gallery_url` local (`/gallery/mediaviewer/{id}`), nút "Mở gallery" thật, nút "Hoàn tất" | tự chuyển sau `qr_download_seconds` (8s) |
| **THANK_YOU** | Lời cảm ơn | tự về `IDLE` sau `thank_you_seconds` (5s), dọn sạch state phiên (thu hồi blob URL video/preview, xoá mảng ảnh) |

Mọi `showError(title, text, retryFn)` đều hiện overlay modal (`#errorPanel`) với 2 nút: **Thử lại** (gọi lại đúng hàm gây lỗi) và **Về màn chờ** (reset toàn bộ session) — đúng tinh thần "fail-forward" của đặc tả.

### 11.3 Video Timelapse — tính năng mới nhất (commit `69e4521f`)

Cơ chế 2 lớp:
1. **Chính (client-side, chất lượng cao)**: trong lúc `CAPTURING`, JS vẽ liên tục khung hình từ `<img>` live-view lên `<canvas>` ẩn (24fps), dùng `canvas.captureStream()` + `MediaRecorder` (ưu tiên codec `vp9`→`vp8`→mặc định) để ghi lại toàn bộ quá trình chụp thành 1 file WebM ngay trên trình duyệt. Khi vào `FINAL_PREVIEW`, video này được phát lại **tốc độ 4x** làm hiệu ứng timelapse — **không tốn round-trip server**.
2. **Dự phòng (server-side)**: nếu trình duyệt không hỗ trợ `MediaRecorder`/canvas capture, gọi `POST /api/framebooth/timelapse` — server dùng OpenCV (`cv2.VideoWriter`, codec `VP80`) dựng video từ chính N+2 ảnh tĩnh đã chụp, có hiệu ứng crossfade giữa các ảnh (13 frame giữ hình + 12 frame chuyển tiếp mỗi ảnh, tổng 1280×720@30fps), trả về file `.webm`.

Nếu người dùng tắt toggle "Nhận file số" ở `PACKAGE_SELECT`, không ghi/dựng video, và QR tải file ở cuối bị disable (hiển thị "File số đã tắt").

### 11.4 Backend `/api/framebooth/*` ([routers/api/framebooth.py](../src/photobooth/routers/api/framebooth.py))

| Method & path | Việc làm |
|---|---|
| `GET /api/framebooth/config` | Trả toàn bộ cấu hình kiosk cho frontend: các hằng số mock timing, giá tiền, danh sách filter, danh sách gói (2/3/4 ảnh) kèm khung mẫu đã phát hiện |
| `GET /api/framebooth/templates/{id}/preview` | Trả file ảnh khung gốc (chưa ghép) |
| `POST /api/framebooth/templates/{id}/composite-preview` | Ghép nhanh N ảnh đã chọn + filter vào khung, trả JPEG preview (resize ≤900px, quality 88) — dùng để xem trước tức thời khi đổi filter |
| `POST /api/framebooth/capture` | Chụp 1 ảnh **thật** từ camera hiện tại (qua `container.acquisition_service`), copy vào `tmp/framebooth/`, lưu vào dict `CAPTURES` trong RAM, trả `id` + `preview_url` |
| `GET /api/framebooth/captures/{id}` | Trả file ảnh đã chụp |
| `POST /api/framebooth/timelapse` | Dựng video fallback từ ảnh tĩnh (mục 11.3) |
| `GET /api/framebooth/timelapses/{id}` | Trả file video |
| `POST /api/framebooth/render` | Ghép ảnh cuối cùng full quality (95%), lưu vào `media/processed_full/`, **tạo `Mediaitem` thật trong DB** (`media_type="collage"`, `show_in_gallery=True`, `pipeline_config` lưu kèm metadata riêng của framebooth: `template_id`, `filter_id`, `capture_ids`, `session_id`, `digital_delivery`) → **ảnh này xuất hiện luôn trong gallery của Classic UI** vì dùng chung `mediacollection_service` |

**Tự động phát hiện khung ảnh (auto-detect frame slots)** — tính năng nổi bật của commit `cb1cc3fe`:
- Khung ảnh (file `.jpg/.png/.webp`) đặt trong `src/photobooth/frame/2/`, `frame/3/`, `frame/4/` (số = số ô ảnh cần ghép).
- `_get_templates()` (có `@lru_cache(maxsize=1)` — **chỉ quét 1 lần lúc chạy, thêm/xoá file khung cần restart app**) dùng OpenCV `connectedComponentsWithStats` để tìm các vùng gần-trắng hoặc gần-đen hình chữ nhật đủ lớn (loại bỏ nhiễu bằng ngưỡng diện tích/tỷ lệ lấp đầy/không chạm biên) — coi đó là các "ô" (placeholder) cần dán ảnh khách vào.
- Nếu số ô tìm được khớp đúng số ảnh kỳ vọng của thư mục (2/3/4) thì tạo `FrameTemplate` (toạ độ từng ô, màu placeholder trắng/đen, tên tự sinh `"Khung {n} anh #{thứ tự}"`); khung không detect đúng số ô sẽ **bị bỏ qua âm thầm** (chỉ log warning).
- Khi ghép ảnh thật (`_render_collage_image`): mỗi ảnh khách được `ImageOps.fit` khít vào đúng ô, dán theo đúng alpha mask của vùng placeholder (`_build_frame_alpha`) rồi phủ khung PNG (đã tách alpha) lên trên cùng — nên khung có thể có viền/hoạ tiết đè lên mép ảnh.

**Bộ lọc màu (5 filter)**: `natural`, `vivid`, `warm`, `mono` (đen trắng), `film` — mỗi filter có **2 cài đặt song song**: `css_filter` (dùng để preview tức thời trên client bằng CSS `filter:`) và hàm PIL tương ứng trong `_apply_filter()` (dùng khi render ảnh thật ở server, đảm bảo preview và kết quả in giống nhau).

Toàn bộ dữ liệu phiên (`CAPTURES`, `TIMELAPSES`) là **dict trong bộ nhớ tiến trình** (`dict[UUID, Path]`), không có TTL/dọn dẹp — nghĩa là: (a) mất hết khi restart app, (b) không hỗ trợ nhiều worker/instance, (c) sẽ phình RAM/đĩa tạm dần theo thời gian chạy nếu không có tiến trình dọn `tmp/framebooth/` bên ngoài.

### 11.5 Khác biệt giữa đặc tả (spec) và triển khai thực tế hiện tại

Đây là phần quan trọng để biết "còn thiếu gì" so với mục tiêu production:

| Hạng mục | Đặc tả (`photobooth-kiosk-ux-spec.md`) | Code thực tế hiện nay |
|---|---|---|
| Thanh toán | VietQR động thật, đối soát qua webhook (Casso/SePay) + polling dự phòng, theo `sessionId` | **Hoàn toàn mock**: QR là hình vẽ giả bằng canvas, tự "thành công" sau 2 giây, không gọi cổng thanh toán nào |
| Máy in | Gọi driver/queue máy in nhiệt thật, xử lý hết giấy/kẹt giấy | **Mock**: chỉ animation CSS + timer, không in ra giấy thật (muốn in thật phải tự nối `ShareService`/lệnh in ở mục 5) |
| QR tải file / QR trong `PRINTING` | Trỏ tới landing page ký sẵn URL (S3/R2), có tính năng phụ "Photo Battle" mời bạn bè vote | QR cũng là hình vẽ giả; link thật đằng sau là route nội bộ `/gallery/mediaviewer/{id}` (chỉ truy cập được trong mạng LAN của kiosk, không phải link public ngoài Internet); chưa có tính năng vote/Photo Battle |
| Lưu trữ file gốc + video cho khách tải | Cloudflare R2, presigned URL, tự xoá theo lifecycle 7/14/30 ngày | **Chưa tích hợp** — mới chỉ có tài liệu kế hoạch [docs/cloudflare-r2-setup.md](../docs/cloudflare-r2-setup.md) (hướng dẫn tạo bucket, CORS, lifecycle, code mẫu Node.js/Python tạo presigned URL) và 3 API đề xuất (`/api/framebooth/r2/upload-url`, `/complete-session`, `/s/{session_id}`) **chưa có trong code** |
| Cấu hình admin (`pricing`, `shotBufferCount`, `captureCountdownSeconds`, `filters[]`, `frameThemes[]`...) | Toàn bộ chỉnh được qua Admin Panel, lưu DB/local | Hiện là **hằng số hard-code** ở đầu file `routers/api/framebooth.py` (`SHOT_BUFFER_COUNT=2`, `CAPTURE_COUNTDOWN_SECONDS=10`, `PRICING={2:50000,3:70000,4:90000}`...) — sửa phải sửa code, không có UI admin riêng cho kiosk (Admin Panel của Classic UI không biết gì về Framebooth) |
| Recoverable session (chống crash/mất điện) | Lưu tiến trình phiên vào SQLite từng bước | Toàn bộ state nằm trong biến JS `state` phía client + dict RAM phía server — **mất hết nếu tải lại trang hoặc app crash giữa chừng** |
| Chọn khung riêng biệt (S8 Frame theme) | Màn hình riêng, nhiều theme theo địa danh/lễ hội, có `validFrom/validTo` | Đã gộp vào bước filter, tự chọn khung mẫu #1 của gói, không có khái niệm "theme theo địa danh/mùa" |
| Ngôn ngữ | Tuỳ chọn bật màn chọn ngôn ngữ | Kiosk chỉ có tiếng Việt (`<html lang="vi">`), không có i18n (khác với Classic UI vốn có đa ngôn ngữ qua Crowdin) |
| 3 tính năng đột phá (Photo Battle, auto social export, Digital Passport đa điểm) | Đề xuất trong đặc tả | Chưa triển khai, chỉ là ý tưởng trong tài liệu |

Tóm lại: **Framebooth hiện là một MVP/demo trình diễn đúng luồng UX** (12 màn hình, timeout, auto-continue, chụp ảnh thật, ghép khung thật, video timelapse thật) nhưng **các phần "tiền thật" (thanh toán, in ấn, lưu trữ đám mây, cấu hình động)** đều đang mock hoặc chưa nối dây, cần hoàn thiện thêm trước khi triển khai thực tế không người trông coi.

---

## 12. Cấu trúc thư mục mã nguồn (tóm tắt)

```
src/photobooth/
├── application.py, container.py, appconfig.py, __main__.py   # khởi tạo app & DI container
├── database/            # models SQLAlchemy, schemas Pydantic, alembic migrations
├── routers/
│   ├── api/              # API công khai: acquisition, actions, config, debug, filter,
│   │                     #   framebooth (kiosk TSL), mediacollection, processing, share, sse, system
│   ├── api_admin/        # API cần đăng nhập: auth, config, enumerate, files, information, multicamera, share
│   ├── media.py, static.py, userdata.py
├── services/
│   ├── acquisition.py, backends/*                # camera
│   ├── processing.py, processor/*                # state machine + job models (image/collage/animation/video/multicamera)
│   ├── mediaprocessing/*                          # pipeline xử lý ảnh/video
│   ├── collection.py, mediacollection/*           # gallery/db/cache/files
│   ├── share.py, gpio.py, system.py, information.py, configuration.py
│   ├── config/*                                   # AppConfig + các group + models (frame overlay, trigger...)
│   └── sse/*                                      # server-sent events
├── plugins/              # commander, gpio_lights, wled, filter_pilgram2, synchronizer
├── utils/                # helper, resize/encode ảnh-video, rembg, hiệu chỉnh đa camera, printer, exceptions...
├── frame/                # khung ảnh dùng bởi cả action "collage" (Classic) lẫn Framebooth (2/3/4 ảnh)
├── demoassets/           # ảnh/font mẫu, symlink vào userdata lúc khởi động
└── photobooth-kiosk-ux-spec.md   # đặc tả UX/kiến trúc kiosk (tiếng Việt, TSL)

src/web/
├── frontend/index.html + assets/*      # SPA Classic đã build (Vue3/Quasar)
├── frontend/framebooth.html            # Kiosk TSL (vanilla JS, 1 file)
├── sharepage/, shareondemand/          # trang chia sẻ tĩnh độc lập

src/tests/            # pytest: services, routers, backends, mediaprocessing steps, plugins, benchmark

docs/
├── cloudflare-r2-setup.md              # kế hoạch tích hợp lưu trữ đám mây (TSL, chưa code)
└── PROJECT_DOCUMENTATION.md            # chính tài liệu này
```

---

## 13. Build, test, chạy dev

- Quản lý package/venv bằng **uv** (`pyproject.toml`, `uv.lock`). Script tiện ích qua `poe` (`poethepoet`): `poe lint` (basedpyright + ruff check/format), `poe format`, `poe test` (pytest + coverage), `poe benchmark`.
- CI (`.github/workflows/`): `pytests.yml`, `linter.yml`, `benchmarks.yml`, `cicd.yml` (build & publish), `dependabot.yml`.
- Test nằm ở `src/tests/tests/` (đơn vị + router) và `src/tests/benchmarks/` (đo hiệu năng resize/encode/filter/xoá nền...). **Chưa thấy test nào riêng cho `routers/api/framebooth.py`** — phần kiosk TSL hiện chưa có coverage tự động.
- Chạy nhanh trên Windows: `./run-local.bat` hoặc `./run-local.ps1` (tự tạo venv, cài `-e .`, chạy `python -m photobooth`, mở trình duyệt `http://127.0.0.1:8000/`).
- Đóng gói: `Dockerfile` ở gốc repo; cũng cài đặt được như **systemd service** trên Linux (`scripts/systemservice/photobooth-app.service`, cài qua `GET /api/system/systemctl/install`).

---

## 14. Tóm tắt nhanh — "app này làm được gì"

- Chụp ảnh/collage/animation/video/wigglegram từ DSLR, Pi camera, webcam hoặc camera ảo (demo), hỗ trợ nhiều camera cùng lúc (1 cho ảnh đẹp, 1 cho live-view).
- Pipeline xử lý ảnh sau chụp: xoá nền AI, ghép nền/khung, filter màu, chèn chữ; xuất GIF/WebP/AVIF/MP4/boomerang.
- Thư viện ảnh (gallery) có cache đa kích thước, xem/xoá/tải/chia sẻ/in, QR chia sẻ, cập nhật realtime qua SSE.
- Cơ chế share/in tuỳ biến bằng lệnh shell, có giới hạn số lượt và chống spam.
- Hệ plugin mở rộng: đèn LED (WLED/GPIO), lệnh ngoài tuỳ biến (commander), đồng bộ cloud qua rclone, thêm bộ lọc màu.
- Điều khiển bằng GPIO vật lý (Raspberry Pi) và phím tắt bàn phím, ngoài cảm ứng/chuột trên UI.
- Admin Panel web đầy đủ: cấu hình mọi thông số qua form tự sinh từ schema, quản lý file, xem log realtime, hiệu chỉnh multicamera, cài đặt như systemd service, đăng nhập JWT.
- **Riêng của fork này**: một trang kiosk tự phục vụ độc lập (Framebooth) mô phỏng đầy đủ luồng bán ảnh in tại điểm du lịch — chọn gói, "thanh toán" (mock), chụp tự động N+2 kiểu, chọn ảnh, chọn filter, ghép khung tự động phát hiện bằng OpenCV, xem trước, "in" (mock), video timelapse dựng từ chính buổi chụp, QR tải (mock) — cùng tài liệu đặc tả UX chi tiết và kế hoạch tích hợp Cloudflare R2 cho việc phát hành ảnh/video thật ra ngoài Internet.
