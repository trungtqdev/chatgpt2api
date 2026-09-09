<h1 align="center">ChatGPT2API</h1>

<p align="center">ChatGPT2API đóng gói và reverse-engineering các API của ChatGPT nền web, cung cấp API / Proxy tương thích chuẩn OpenAI chuyên phục vụ nhu cầu tạo ảnh, chỉnh sửa ảnh và chỉnh sửa nhiều ảnh tham chiếu; tích hợp sẵn giao diện web tạo ảnh trực quan, quản lý nhóm tài khoản với nhiều cách nhập, hỗ trợ triển khai tự lưu trữ qua Docker.</p>

> [!WARNING]
> Tuyên bố miễn trừ trách nhiệm:
>
> Dự án này nghiên cứu reverse-engineering các giao diện tạo văn bản, tạo ảnh và chỉnh sửa ảnh trên ChatGPT web, chỉ phục vụ mục đích học tập cá nhân, nghiên cứu kỹ thuật và trao đổi phi thương mại.
>
> - Nghiêm cấm sử dụng dự án cho bất kỳ mục đích thương mại, sinh lời, thao tác hàng loạt, lạm dụng tự động hóa hoặc gọi quy mô lớn.
> - Nghiêm cấm sử dụng dự án để phá hoại trật tự thị trường, cạnh tranh không lành mạnh, bán lại dịch vụ hoặc bất kỳ hành vi nào vi phạm điều khoản dịch vụ của OpenAI hoặc pháp luật hiện hành.
> - Nghiêm cấm sử dụng dự án để tạo, phát tán hoặc hỗ trợ tạo nội dung bất hợp pháp, bạo lực, khiêu dâm, liên quan đến trẻ vị thành niên, hoặc lừa đảo, quấy rối.
> - Người dùng tự chịu mọi rủi ro, bao gồm nhưng không giới hạn ở việc tài khoản bị giới hạn, khóa tạm thời hoặc khóa vĩnh viễn cũng như trách nhiệm pháp lý phát sinh do sử dụng sai mục đích.
> - Sử dụng dự án này đồng nghĩa với việc bạn đã hiểu rõ và đồng ý với toàn bộ nội dung của tuyên bố này.

> [!IMPORTANT]
> Dự án dựa trên reverse-engineering hệ thống ChatGPT web, có nguy cơ tài khoản bị giới hạn hoặc bị khóa. Vui lòng KHÔNG sử dụng tài khoản quan trọng, tài khoản chính hoặc có giá trị cao để thử nghiệm.

## Bắt đầu nhanh

Image Docker hỗ trợ cả `linux/amd64` và `linux/arm64`, tự động tải phiên bản phù hợp trên máy chủ x86 cũng như ARM Linux / Apple Silicon.

### Chạy bằng Docker

```bash
git clone git@github.com:trungtqdev/chatgpt2api.git
cd chatgpt2api
docker compose up -d
```

Trước khi khởi động, hãy thiết lập `auth-key` trong `config.json` hoặc ghi đè thông qua biến môi trường `CHATGPT2API_AUTH_KEY` trong `docker-compose.yml`.

- Bảng điều khiển Web: `http://localhost:3300` (hoặc domain cấu hình qua Nginx)
- Địa chỉ API: `http://localhost:3300/v1`
- Thư mục dữ liệu: `./data`

### Phát triển cục bộ (Local Development)

Khởi động Backend:

```bash
git clone git@github.com:trungtqdev/chatgpt2api.git
cd chatgpt2api
uv sync
uv run main.py
```

Khởi động Frontend:

```bash
cd chatgpt2api/web
bun install
bun run dev
```

### Cấu hình Backend lưu trữ (Storage Backend)

Hỗ trợ chuyển đổi phương thức lưu trữ thông qua biến môi trường `STORAGE_BACKEND`:

- `json` - File JSON cục bộ (mặc định)
- `sqlite` - Cơ sở dữ liệu SQLite cục bộ
- `postgres` - PostgreSQL bên ngoài (cần cấu hình `DATABASE_URL`)
- `git` - Kho lưu trữ Git riêng tư (cần cấu hình `GIT_REPO_URL` và `GIT_TOKEN`)

Ví dụ: Sử dụng PostgreSQL

```yaml
environment:
  - STORAGE_BACKEND=postgres
  - DATABASE_URL=postgresql://user:password@host:5432/dbname
```

## Tính năng nổi bật

### Khả năng tương thích API
- Tương thích endpoint tạo ảnh `POST /v1/images/generations`
- Tương thích endpoint chỉnh sửa ảnh `POST /v1/images/edits`
- Tương thích endpoint `POST /v1/chat/completions` (dành cho kịch bản tạo ảnh)
- Tương thích endpoint `POST /v1/responses` (dành cho kịch bản gọi công cụ tạo ảnh)
- `GET /v1/models` trả về danh sách model: `gpt-image-2`, `codex-gpt-image-2`, `auto`, `gpt-5`, `gpt-5-1`, `gpt-5-2`, `gpt-5-3`, `gpt-5-3-mini`, `gpt-5-mini`
- Hỗ trợ tham số `n` để trả về nhiều ảnh tạo cùng lúc
- Hỗ trợ endpoint vẽ ảnh trong Codex (chỉ khả dụng cho tài khoản `Plus` / `Team` / `Pro`), alias model là `codex-gpt-image-2`, giúp tận dụng cả 2 hạn mức tạo ảnh song song trên cùng 1 tài khoản

### Tính năng vẽ ảnh trực tuyến (Web Studio)
- Bàn làm việc vẽ ảnh trực tuyến tích hợp sẵn, hỗ trợ tạo ảnh mới, chỉnh sửa ảnh và chỉnh sửa nhiều ảnh tham chiếu
- Hỗ trợ lựa chọn linh hoạt giữa các model: `gpt-image-2`, `codex-gpt-image-2`, `auto`, v.v.
- Hỗ trợ tải lên ảnh tham chiếu trong chế độ chỉnh sửa
- Giao diện hỗ trợ tạo đồng thời nhiều ảnh theo yêu cầu
- Lưu trữ lịch sử hội thoại tạo ảnh cục bộ, hỗ trợ xem lại, đổi tên và xóa
- Hỗ trợ bộ nhớ đệm (caching) URL hình ảnh phía máy chủ

### Quản lý nhóm tài khoản (Account Pool)
- Tự động làm mới email tài khoản, loại gói, hạn mức và thời gian hồi phục
- Tự động luân phiên (round-robin) các tài khoản khả dụng khi tạo ảnh
- Tự động phát hiện và loại bỏ các Token hết hạn hoặc bất thường
- Định kỳ kiểm tra và làm mới trạng thái các tài khoản bị giới hạn tần suất (rate-limit)
- Hỗ trợ cấu hình Proxy toàn cục: HTTP / HTTPS / SOCKS5 / SOCKS5H
- Hỗ trợ tìm kiếm, lọc trạng thái, làm mới hàng loạt, xuất file và chỉnh sửa tài khoản
- Hỗ trợ 4 phương thức nhập tài khoản: file CPA JSON, máy chủ CPA từ xa, máy chủ `sub2api`, hoặc nhập trực tiếp `access_token`

## Ảnh chụp màn hình

Giao diện tạo ảnh:

![image](assets/image.png)

Chỉnh sửa ảnh:

![image](assets/image_edit.png)

Tích hợp vào Cherry Studio:

![image](assets/chery_studio.png)

Quản lý nhóm tài khoản:

![image](assets/account_pool.png)

Tích hợp vào New API:

![image](assets/new_api.png)

## Hướng dẫn API

Tất cả các endpoint AI đều yêu cầu Header xác thực:

```http
Authorization: Bearer <auth-key>
```

<details>
<summary><code>GET /v1/models</code></summary>
<br>

Trả về danh sách các model tạo ảnh hiện có.

```bash
curl http://localhost:3300/v1/models   -H "Authorization: Bearer <auth-key>"
```

<details>
<summary>Giải thích</summary>
<br>

| Trường | Giải thích |
|:---|:---|
| Model trả về | `gpt-image-2`, `codex-gpt-image-2`, `auto`, `gpt-5`, `gpt-5-1`, `gpt-5-2`, `gpt-5-3`, `gpt-5-3-mini`, `gpt-5-mini` |
| Ứng dụng | Dùng kết nối trực tiếp vào Cherry Studio, NextChat, New API hoặc các client tương thích OpenAI |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/images/generations</code></summary>
<br>

Giao diện tạo ảnh tương thích OpenAI (Text-to-Image).

```bash
curl http://localhost:3300/v1/images/generations   -H "Content-Type: application/json"   -H "Authorization: Bearer <auth-key>"   -d '{
    "model": "gpt-image-2",
    "prompt": "Một chú mèo dễ thương lơ lửng ngoài vũ trụ",
    "n": 1,
    "response_format": "b64_json"
  }'
```

<details>
<summary>Mô tả tham số</summary>
<br>

| Tham số | Mô tả |
|:---|:---|
| `model` | Model tạo ảnh (khuyến nghị dùng `gpt-image-2`) |
| `prompt` | Câu lệnh mô tả hình ảnh cần tạo |
| `n` | Số lượng ảnh cần tạo (giới hạn từ 1 đến 4) |
| `response_format` | Định dạng phản hồi, mặc định là `b64_json` |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/images/edits</code></summary>
<br>

Giao diện chỉnh sửa ảnh tương thích OpenAI (Image-to-Image).

```bash
curl http://localhost:3300/v1/images/edits   -H "Authorization: Bearer <auth-key>"   -F "model=gpt-image-2"   -F "prompt=Chuyển bức ảnh này sang phong cách cyberpunk ban đêm"   -F "n=1"   -F "image=@./input.png"
```

<details>
<summary>Mô tả tham số</summary>
<br>

| Tham số | Mô tả |
|:---|:---|
| `model` | Model tạo ảnh, ví dụ `gpt-image-2` |
| `prompt` | Câu lệnh mô tả yêu cầu chỉnh sửa |
| `n` | Số lượng ảnh kết quả |
| `image` | File ảnh cần chỉnh sửa, tải lên qua multipart/form-data |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/chat/completions</code></summary>
<br>

Giao diện Chat Completions tương thích OpenAI dành cho kịch bản tạo ảnh.

```bash
curl http://localhost:3300/v1/chat/completions   -H "Content-Type: application/json"   -H "Authorization: Bearer <auth-key>"   -d '{
    "model": "gpt-image-2",
    "messages": [
      {
        "role": "user",
        "content": "Vẽ cho tôi một bức tranh thành phố tương lai cyberpunk lúc trời mưa"
      }
    ],
    "n": 1
  }'
```

<details>
<summary>Mô tả tham số</summary>
<br>

| Tham số | Mô tả |
|:---|:---|
| `model` | Model ảnh |
| `messages` | Mảng tin nhắn chứa yêu cầu vẽ ảnh |
| `n` | Số lượng ảnh tạo |

<br>
</details>
</details>

<details>
<summary><code>POST /v1/responses</code></summary>
<br>

Giao diện Responses API tương thích gọi công cụ tạo ảnh.

```bash
curl http://localhost:3300/v1/responses   -H "Content-Type: application/json"   -H "Authorization: Bearer <auth-key>"   -d '{
    "model": "gpt-5",
    "input": "Tạo một bức tranh về đường chân trời thành phố tương lai",
    "tools": [
      {
        "type": "image_generation"
      }
    ]
  }'
```

<br>
</details>
