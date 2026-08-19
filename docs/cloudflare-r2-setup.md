# Cloudflare R2 setup cho Photobooth Kiosk

Tài liệu này dùng cho flow: khách chụp ảnh tại kiosk, app render ảnh ghép + video timelapse, upload bộ file lên Cloudflare R2, sau đó hiển thị QR để khách tải trong 7-30 ngày.

Nguồn chính thức đã đối chiếu ngày 2026-08-18:

- R2 pricing: https://developers.cloudflare.com/r2/pricing/
- Create buckets: https://developers.cloudflare.com/r2/buckets/create-buckets/
- Configure CORS: https://developers.cloudflare.com/r2/buckets/cors/
- Object lifecycle rules: https://developers.cloudflare.com/r2/buckets/object-lifecycles/
- S3 API compatibility: https://developers.cloudflare.com/r2/api/s3/api/
- Presigned URLs: https://developers.cloudflare.com/r2/api/s3/presigned-urls/
- Upload objects: https://developers.cloudflare.com/r2/objects/upload-objects/

## 1. Kiến trúc đề xuất

Khuyến nghị cho kiosk du lịch: dùng bucket private, không để lộ R2 key ở frontend.

Flow production:

1. Kiosk chụp toàn bộ ảnh gốc local.
2. Backend render `final.jpg` và `timelapse.mp4`.
3. Backend tạo presigned PUT URL cho từng file.
4. Kiosk upload trực tiếp lên R2 bằng URL tạm thời.
5. QR không trỏ thẳng vào object vĩnh viễn. QR trỏ tới landing page của mình, ví dụ `https://photo.example.com/s/PB123456`.
6. Landing page gọi backend để lấy presigned GET URL ngắn hạn cho từng file.
7. R2 lifecycle tự xoá object sau 7, 14 hoặc 30 ngày.

Cấu trúc key nên dùng:

```text
sessions/2026/08/PB123456/originals/shot-01.jpg
sessions/2026/08/PB123456/originals/shot-02.jpg
sessions/2026/08/PB123456/final/final-frame.jpg
sessions/2026/08/PB123456/video/timelapse.mp4
sessions/2026/08/PB123456/manifest.json
```

Lý do chọn R2:

- R2 không tính phí egress Internet theo bảng giá hiện tại, rất hợp bài toán khách quét QR tải MP4.
- Hỗ trợ S3-compatible API nên dùng được AWS SDK, boto3, presigned URL.
- Có lifecycle rule xoá object theo tuổi file.
- Có custom domain và Cloudflare Cache nếu sau này cần phát file công khai hoặc tối ưu tải ở Việt Nam.

## 2. Tạo bucket

Cách nhanh bằng Wrangler:

```bash
npm install -D wrangler
npx wrangler login
npx wrangler r2 bucket create tsl-photobooth-prod
npx wrangler r2 bucket list
```

Hoặc làm trong Dashboard:

1. Vào Cloudflare Dashboard.
2. Chọn tài khoản Cloudflare.
3. Vào `R2 Object Storage`.
4. Chọn `Create bucket`.
5. Đặt tên bucket, ví dụ `tsl-photobooth-prod`.
6. Giữ bucket private cho bản production.

Tên bucket chỉ nên dùng chữ thường, số và dấu gạch ngang.

## 3. Tạo R2 API token

Trong Cloudflare Dashboard:

1. Vào `R2 Object Storage`.
2. Chọn `Manage R2 API Tokens`.
3. Chọn `Create API token`.
4. Quyền tối thiểu cho backend upload/download: `Object Read & Write`.
5. Scope nên giới hạn đúng bucket `tsl-photobooth-prod`.
6. Lưu lại:
   - `Account ID`
   - `Access Key ID`
   - `Secret Access Key`

Tuyệt đối không đưa `Access Key ID` và `Secret Access Key` vào file frontend.

## 4. Biến môi trường cho app

Tạo `.env` hoặc cấu hình trong service manager:

```env
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_BUCKET=tsl-photobooth-prod
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key
R2_PUBLIC_BASE_URL=https://photo.example.com
R2_UPLOAD_EXPIRES_SECONDS=900
R2_DOWNLOAD_EXPIRES_SECONDS=300
R2_RETENTION_DAYS=7
```

Endpoint S3-compatible của R2:

```text
https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

Region dùng với SDK là:

```text
auto
```

## 5. Cấu hình CORS

CORS cần thiết nếu browser hoặc kiosk frontend upload/download trực tiếp bằng presigned URL.

Dashboard:

1. Vào `R2 Object Storage`.
2. Chọn bucket.
3. Vào `Settings`.
4. Tìm phần `CORS Policy`.
5. Dán JSON bên dưới, đổi domain cho đúng môi trường.

```json
[
  {
    "AllowedOrigins": [
      "http://127.0.0.1:8000",
      "http://localhost:8000",
      "https://photo.example.com"
    ],
    "AllowedMethods": ["PUT"],
    "AllowedHeaders": ["Content-Type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  },
  {
    "AllowedOrigins": [
      "http://127.0.0.1:8000",
      "http://localhost:8000",
      "https://photo.example.com"
    ],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag", "Content-Length"],
    "MaxAgeSeconds": 3600
  }
]
```

Production nên thay `localhost` bằng domain thật của kiosk/admin. Không dùng `"*"` cho `AllowedOrigins` nếu file có tính riêng tư.

## 6. Lifecycle tự xoá file

Khuyến nghị:

- Demo/MVP: xoá sau 7 ngày.
- Điểm du lịch lưu lượng cao: 7-14 ngày.
- Gói premium hoặc sự kiện: 30 ngày.

Dashboard:

1. Vào bucket `tsl-photobooth-prod`.
2. Vào `Settings`.
3. Chọn `Object Lifecycle Rules`.
4. Chọn `Add rule`.
5. Rule name: `delete-photobooth-sessions-after-7-days`.
6. Prefix: `sessions/`.
7. Action: expire/delete objects.
8. Age: `7` days.
9. Save.

Wrangler:

Tạo file `r2-lifecycle.json`:

```json
{
  "Rules": [
    {
      "ID": "delete-photobooth-sessions-after-7-days",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "sessions/"
      },
      "Expiration": {
        "Days": 7
      }
    },
    {
      "ID": "abort-incomplete-uploads-after-1-day",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "sessions/"
      },
      "AbortIncompleteMultipartUpload": {
        "DaysAfterInitiation": 1
      }
    }
  ]
}
```

Áp dụng:

```bash
npx wrangler r2 bucket lifecycle set tsl-photobooth-prod --file r2-lifecycle.json
npx wrangler r2 bucket lifecycle list tsl-photobooth-prod
```

Cloudflare ghi chú object thường được xoá trong vòng khoảng 24 giờ sau thời điểm hết hạn lifecycle. Vì vậy UI nên ghi “link còn hiệu lực đến ngày X”, không nên hứa xoá đúng từng giây.

## 7. Code mẫu Node.js tạo presigned URL

Cài package:

```bash
npm install @aws-sdk/client-s3 @aws-sdk/s3-request-presigner
```

`r2-presign.mjs`:

```js
import crypto from "node:crypto";
import { GetObjectCommand, PutObjectCommand, S3Client } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

const bucket = process.env.R2_BUCKET;

const s3 = new S3Client({
  region: "auto",
  endpoint: `https://${process.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
  credentials: {
    accessKeyId: process.env.R2_ACCESS_KEY_ID,
    secretAccessKey: process.env.R2_SECRET_ACCESS_KEY,
  },
});

function safeName(filename) {
  return filename.toLowerCase().replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
}

function sessionPrefix(sessionId, now = new Date()) {
  const year = now.getUTCFullYear();
  const month = String(now.getUTCMonth() + 1).padStart(2, "0");
  return `sessions/${year}/${month}/${sessionId}`;
}

export async function createUploadUrl({ sessionId, folder, filename, contentType }) {
  const allowedTypes = new Set(["image/jpeg", "image/png", "video/mp4", "application/json"]);
  if (!allowedTypes.has(contentType)) {
    throw new Error(`Unsupported content type: ${contentType}`);
  }

  const key = `${sessionPrefix(sessionId)}/${folder}/${crypto.randomUUID()}-${safeName(filename)}`;
  const command = new PutObjectCommand({
    Bucket: bucket,
    Key: key,
    ContentType: contentType,
    Metadata: {
      session_id: sessionId,
    },
  });

  const url = await getSignedUrl(s3, command, { expiresIn: 900 });
  return {
    key,
    url,
    method: "PUT",
    headers: {
      "Content-Type": contentType,
    },
  };
}

export async function createDownloadUrl(key) {
  const command = new GetObjectCommand({
    Bucket: bucket,
    Key: key,
  });

  return getSignedUrl(s3, command, { expiresIn: 300 });
}
```

Client upload:

```js
async function uploadWithPresignedUrl(file, presigned) {
  const response = await fetch(presigned.url, {
    method: "PUT",
    headers: presigned.headers,
    body: file,
  });

  if (!response.ok) {
    throw new Error(`R2 upload failed: ${response.status}`);
  }

  return {
    key: presigned.key,
    etag: response.headers.get("ETag"),
  };
}
```

## 8. Code mẫu Python tạo presigned URL

Cài package:

```bash
pip install boto3
```

`r2_presign.py`:

```python
import os
import re
import uuid
from datetime import datetime, timezone

import boto3


BUCKET = os.environ["R2_BUCKET"]

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
)


def safe_name(filename: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", filename).strip("-").lower()
    return value or "file"


def session_prefix(session_id: str) -> str:
    now = datetime.now(timezone.utc)
    return f"sessions/{now:%Y/%m}/{session_id}"


def create_upload_url(session_id: str, folder: str, filename: str, content_type: str) -> dict:
    allowed_types = {"image/jpeg", "image/png", "video/mp4", "application/json"}
    if content_type not in allowed_types:
        raise ValueError(f"unsupported content type: {content_type}")

    key = f"{session_prefix(session_id)}/{folder}/{uuid.uuid4()}-{safe_name(filename)}"
    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": BUCKET,
            "Key": key,
            "ContentType": content_type,
            "Metadata": {"session_id": session_id},
        },
        ExpiresIn=900,
        HttpMethod="PUT",
    )
    return {"key": key, "url": url, "method": "PUT", "headers": {"Content-Type": content_type}}


def create_download_url(key: str) -> str:
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=300,
        HttpMethod="GET",
    )
```

## 9. Gắn vào flow photobooth

Backend nên có 3 nhóm API:

```text
POST /api/framebooth/r2/upload-url
POST /api/framebooth/r2/complete-session
GET  /s/{session_id}
```

`upload-url`:

- Input: `session_id`, `folder`, `filename`, `content_type`.
- Output: presigned PUT URL.
- Chỉ cho phép folder hợp lệ: `originals`, `final`, `video`, `manifest`.

`complete-session`:

- Lưu manifest vào database/local JSON.
- Manifest gồm key ảnh gốc, key ảnh final, key video, ngày hết hạn.
- Nếu mất mạng, đưa session vào local retry queue.

`/s/{session_id}`:

- Trang landing cho QR.
- Không expose R2 key.
- Khi khách bấm tải, backend tạo presigned GET URL mới, thời hạn ngắn 5-15 phút.

Manifest mẫu:

```json
{
  "session_id": "PB123456",
  "expires_at": "2026-08-25T00:00:00Z",
  "files": {
    "originals": [
      "sessions/2026/08/PB123456/originals/shot-01.jpg"
    ],
    "final": "sessions/2026/08/PB123456/final/final-frame.jpg",
    "timelapse": "sessions/2026/08/PB123456/video/timelapse.mp4"
  }
}
```

## 10. Checklist trước khi chạy thật

- Bucket private.
- API token chỉ có quyền đúng bucket.
- CORS chỉ cho domain kiosk/admin thật.
- Presigned PUT giới hạn `Content-Type`.
- Presigned URL upload ngắn, khoảng 15 phút.
- Presigned URL download ngắn, khoảng 5-15 phút.
- QR trỏ về landing page của mình, không trỏ trực tiếp presigned URL dài.
- Lifecycle bật cho prefix `sessions/`.
- Có local retry queue khi mất mạng.
- Có job dọn local file sau khi upload thành công.
- Có log session: `session_id`, payment status, object keys, upload status, print status.

