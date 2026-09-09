"use client";

import { useEffect, useState } from "react";
import {
  Check,
  Code2,
  Copy,
  ExternalLink,
  HelpCircle,
  Key,
  Layers,
  LoaderCircle,
  Monitor,
  Rocket,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuthGuard } from "@/lib/use-auth-guard";

function CopyButton({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success(label ? `Đã sao chép ${label}` : "Đã sao chép vào bộ nhớ tạm");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Không thể sao chép");
    }
  };

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="h-8 gap-1.5 rounded-lg border-stone-200 bg-white px-2.5 text-xs font-medium text-stone-700 hover:bg-stone-50 hover:text-stone-900"
      onClick={handleCopy}
    >
      {copied ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
      <span>{copied ? "Đã chép" : "Sao chép"}</span>
    </Button>
  );
}

function CodeBlock({ code, language = "bash" }: { code: string; language?: string }) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-stone-800 bg-stone-950 text-stone-100">
      <div className="flex items-center justify-between border-b border-stone-800 bg-stone-900/60 px-4 py-2 text-xs text-stone-400">
        <span className="font-mono uppercase tracking-wider">{language}</span>
        <CopyButton text={code} label="đoạn mã" />
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-xs leading-relaxed text-stone-200">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export default function DocsPage() {
  const { isCheckingAuth, session } = useAuthGuard();
  const [baseUrl, setBaseUrl] = useState("https://apikeygpt.pagee.io.vn/v1");
  const [activeTab, setActiveTab] = useState<"quickstart" | "clients" | "api" | "models" | "admin" | "faq">("quickstart");

  useEffect(() => {
    if (typeof window !== "undefined") {
      setBaseUrl(`${window.location.origin}/v1`);
    }
  }, []);

  if (isCheckingAuth || !session) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <LoaderCircle className="size-6 animate-spin text-stone-400" />
      </div>
    );
  }

  const curlGenCode = `curl ${baseUrl}/images/generations \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer <API_KEY_CUA_BAN>" \\
  -d '{
    "model": "gpt-image-2",
    "prompt": "Một chú mèo con phong cách anime đang đọc sách dưới ánh trăng huyền ảo",
    "n": 1,
    "response_format": "b64_json"
  }'`;

  const curlEditCode = `curl ${baseUrl}/images/edits \\
  -H "Authorization: Bearer <API_KEY_CUA_BAN>" \\
  -F "model=gpt-image-2" \\
  -F "prompt=Chuyển bức ảnh này sang phong cách tranh sơn dầu hoàng hôn" \\
  -F "n=1" \\
  -F "image=@./input.png"`;

  const pythonCode = `from openai import OpenAI

client = OpenAI(
    base_url="${baseUrl}",
    api_key="<API_KEY_CUA_BAN>",
)

response = client.images.generate(
    model="gpt-image-2",
    prompt="Một phi hành gia đang lướt sóng giữa vũ trụ huyền ảo rực rỡ",
    n=1,
)

# Kết quả ảnh trả về dưới dạng base64
image_base64 = response.data[0].b64_json
print("Tạo ảnh thành công!")`;

  const jsCode = `import OpenAI from "openai";

const openai = new OpenAI({
  baseURL: "${baseUrl}",
  apiKey: "<API_KEY_CUA_BAN>",
});

async function main() {
  const response = await openai.images.generate({
    model: "gpt-image-2",
    prompt: "Thành phố cyberpunk lung linh lúc trời mưa ban đêm",
    n: 1,
  });

  console.log("Ảnh:", response.data[0].b64_json);
}

main();`;

  const curlChatCode = `curl ${baseUrl}/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer <API_KEY_CUA_BAN>" \\
  -d '{
    "model": "gpt-image-2",
    "messages": [
      {
        "role": "user",
        "content": "Vẽ cho tôi một bức tranh phong cảnh mùa thu Hà Nội tuyệt đẹp"
      }
    ]
  }'`;

  return (
    <div className="space-y-6 pb-12">
      {/* Header Banner */}
      <div className="rounded-3xl border border-stone-200/80 bg-gradient-to-br from-white/90 via-stone-50/70 to-stone-100/50 p-6 shadow-sm backdrop-blur-sm sm:p-8">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="gap-1 bg-stone-900 text-white hover:bg-stone-800">
                <Sparkles className="size-3" />
                <span>ChatGPT2API Docs</span>
              </Badge>
              <Badge variant="outline" className="border-stone-300 text-stone-600">
                OpenAI-Compatible
              </Badge>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-stone-900 sm:text-3xl">
              Hướng dẫn sử dụng & Tài liệu API
            </h1>
            <p className="max-w-3xl text-sm leading-relaxed text-stone-600">
              Hướng dẫn toàn diện cách kết nối API tạo ảnh và chỉnh sửa ảnh tương thích OpenAI, tích hợp vào các công cụ phổ biến (Cherry Studio, NextChat, One API, Dify...) và quản lý tài khoản.
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <a
              href="https://github.com/trungtqdev/chatgpt2api"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl border border-stone-200 bg-white px-4 py-2 text-xs font-semibold text-stone-800 shadow-sm transition hover:bg-stone-50"
            >
              <span>GitHub Repo</span>
              <ExternalLink className="size-3.5 text-stone-400" />
            </a>
          </div>
        </div>

        {/* Quick parameters bar */}
        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="flex items-center justify-between rounded-2xl border border-stone-200/80 bg-white p-3.5 shadow-xs">
            <div className="min-w-0 pr-2">
              <div className="text-[11px] font-medium text-stone-400 uppercase tracking-wider">Base URL</div>
              <div className="truncate font-mono text-xs font-semibold text-stone-900">{baseUrl}</div>
            </div>
            <CopyButton text={baseUrl} label="Base URL" />
          </div>

          <div className="flex items-center justify-between rounded-2xl border border-stone-200/80 bg-white p-3.5 shadow-xs">
            <div className="min-w-0 pr-2">
              <div className="text-[11px] font-medium text-stone-400 uppercase tracking-wider">Model Khuyên dùng</div>
              <div className="truncate font-mono text-xs font-semibold text-stone-900">gpt-image-2</div>
            </div>
            <CopyButton text="gpt-image-2" label="tên Model" />
          </div>

          <div className="flex items-center justify-between rounded-2xl border border-stone-200/80 bg-white p-3.5 shadow-xs">
            <div className="min-w-0 pr-2">
              <div className="text-[11px] font-medium text-stone-400 uppercase tracking-wider">Auth Header</div>
              <div className="truncate font-mono text-xs font-semibold text-stone-900">Authorization: Bearer</div>
            </div>
            <CopyButton text="Authorization: Bearer <API_KEY>" label="Auth Header" />
          </div>
        </div>
      </div>

      {/* Navigation tabs */}
      <div className="flex flex-wrap gap-2 border-b border-stone-200 pb-2">
        <button
          type="button"
          onClick={() => setActiveTab("quickstart")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition ${
            activeTab === "quickstart"
              ? "bg-stone-900 text-white shadow-sm"
              : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"
          }`}
        >
          <Rocket className="size-4" />
          <span>Bắt đầu nhanh</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("clients")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition ${
            activeTab === "clients"
              ? "bg-stone-900 text-white shadow-sm"
              : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"
          }`}
        >
          <Monitor className="size-4" />
          <span>Tích hợp phần mềm</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("api")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition ${
            activeTab === "api"
              ? "bg-stone-900 text-white shadow-sm"
              : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"
          }`}
        >
          <Code2 className="size-4" />
          <span>Mẫu gọi API (cURL & SDK)</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("models")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition ${
            activeTab === "models"
              ? "bg-stone-900 text-white shadow-sm"
              : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"
          }`}
        >
          <Layers className="size-4" />
          <span>Danh sách Model</span>
        </button>

        {session.role === "admin" ? (
          <button
            type="button"
            onClick={() => setActiveTab("admin")}
            className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition ${
              activeTab === "admin"
                ? "bg-stone-900 text-white shadow-sm"
                : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"
            }`}
          >
            <Users className="size-4" />
            <span>Quản trị tài khoản</span>
          </button>
        ) : null}

        <button
          type="button"
          onClick={() => setActiveTab("faq")}
          className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition ${
            activeTab === "faq"
              ? "bg-stone-900 text-white shadow-sm"
              : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"
          }`}
        >
          <HelpCircle className="size-4" />
          <span>Câu hỏi thường gặp</span>
        </button>
      </div>

      {/* TAB CONTENT: QUICKSTART */}
      {activeTab === "quickstart" && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="border-stone-200 bg-white/80 backdrop-blur-sm lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg text-stone-900">
                <Rocket className="size-5 text-stone-700" />
                <span>3 Bước bắt đầu sử dụng</span>
              </CardTitle>
              <CardDescription>
                Quy trình nhanh chóng để tích hợp và tạo ảnh từ ChatGPT2API
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex gap-4">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-stone-900 font-bold text-white text-xs">
                  1
                </div>
                <div className="space-y-1.5">
                  <h3 className="font-semibold text-stone-900">Lấy API Key xác thực</h3>
                  <p className="text-xs leading-relaxed text-stone-600">
                    Nếu bạn là <strong>Quản trị viên</strong>, bạn có thể dùng trực tiếp mã <code>CHATGPT2API_AUTH_KEY</code> hoặc vào mục <strong>Cài đặt → Khóa người dùng</strong> để tạo khóa mới. Nếu bạn là <strong>Người dùng</strong>, hãy liên hệ quản trị viên để nhận khóa API của mình.
                  </p>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-stone-900 font-bold text-white text-xs">
                  2
                </div>
                <div className="space-y-1.5">
                  <h3 className="font-semibold text-stone-900">Điền Base URL vào ứng dụng</h3>
                  <p className="text-xs leading-relaxed text-stone-600">
                    Sử dụng địa chỉ API chuẩn dưới đây cho mọi phần mềm hoặc thư viện OpenAI client:
                  </p>
                  <div className="flex items-center justify-between rounded-xl border border-stone-200 bg-stone-50 p-2.5 font-mono text-xs text-stone-800">
                    <span>{baseUrl}</span>
                    <CopyButton text={baseUrl} label="Base URL" />
                  </div>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-stone-900 font-bold text-white text-xs">
                  3
                </div>
                <div className="space-y-1.5">
                  <h3 className="font-semibold text-stone-900">Chọn Model và bắt đầu vẽ</h3>
                  <p className="text-xs leading-relaxed text-stone-600">
                    Chọn model <code>gpt-image-2</code> để có chất lượng tốt nhất. Nhập prompt mô tả bức ảnh và gửi yêu cầu! Hệ thống sẽ tự động điều phối qua nhóm tài khoản ChatGPT để trả về ảnh hoàn chỉnh.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Quick Info Box */}
          <div className="space-y-4">
            <Card className="border-stone-200 bg-white/80">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-stone-900 flex items-center gap-1.5">
                  <Key className="size-4 text-stone-700" />
                  <span>Xác thực yêu cầu</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-xs text-stone-600">
                <p>Mọi request gửi tới API đều cần Header:</p>
                <div className="rounded-lg bg-stone-100 p-2 font-mono text-[11px] text-stone-900">
                  Authorization: Bearer &lt;API_KEY&gt;
                </div>
                <p className="text-[11px] text-stone-500">
                  Chấp nhận cả khóa quản trị viên (Admin Key) và khóa người dùng (User Key).
                </p>
              </CardContent>
            </Card>

            <Card className="border-stone-200 bg-white/80">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-semibold text-stone-900 flex items-center gap-1.5">
                  <ShieldCheck className="size-4 text-emerald-600" />
                  <span>Tự động xoay vòng & Dự phòng</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-stone-600 space-y-2">
                <p>
                  Hệ thống tích hợp sẵn thuật toán <strong>Round-Robin</strong> tự động phân phối tải đều qua các tài khoản ChatGPT khả dụng.
                </p>
                <p>
                  Nếu tài khoản bị giới hạn tần suất (Rate Limit 429), hệ thống sẽ tự động chuyển sang tài khoản khác mà không làm gián đoạn yêu cầu.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* TAB CONTENT: CLIENTS */}
      {activeTab === "clients" && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* Cherry Studio */}
          <Card className="border-stone-200 bg-white/80">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base text-stone-900">Cherry Studio</CardTitle>
                <Badge variant="outline" className="text-xs font-normal">Desktop App</Badge>
              </div>
              <CardDescription>Hướng dẫn tích hợp vào phần mềm Cherry Studio</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-xs text-stone-600">
              <ol className="list-decimal space-y-2 pl-4">
                <li>Mở <strong>Cài đặt (Settings)</strong> → <strong>Nhà cung cấp mô hình (Model Providers)</strong>.</li>
                <li>Chọn <strong>OpenAI</strong> (hoặc bấm <strong>Thêm nhà cung cấp tùy chỉnh</strong>).</li>
                <li>Tại mục <strong>API Key</strong>: Dán khóa API của bạn.</li>
                <li>Tại mục <strong>API Base URL</strong>: Dán <code>{baseUrl}</code></li>
                <li>Tại danh sách mô hình, nhấn <strong>Thêm mô hình (Add Model)</strong>, nhập ID: <code>gpt-image-2</code>.</li>
                <li>Lưu lại và mở phòng trò chuyện để bắt đầu vẽ ảnh!</li>
              </ol>
            </CardContent>
          </Card>

          {/* NextChat */}
          <Card className="border-stone-200 bg-white/80">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base text-stone-900">NextChat / ChatGPT-Next-Web</CardTitle>
                <Badge variant="outline" className="text-xs font-normal">Web / App</Badge>
              </div>
              <CardDescription>Cấu hình trong giao diện NextChat</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-xs text-stone-600">
              <ol className="list-decimal space-y-2 pl-4">
                <li>Mở menu <strong>Cài đặt</strong> ở góc dưới bên trái.</li>
                <li>Tại mục <strong>Địa chỉ máy chủ (Endpoint)</strong>: Nhập <code>{baseUrl.replace(/\/v1$/, "")}</code></li>
                <li>Tại mục <strong>API Key</strong>: Nhập khóa API của bạn.</li>
                <li>Tại mục <strong>Mô hình tùy chỉnh (Custom Models)</strong>: Nhập thêm <code>+gpt-image-2</code></li>
                <li>Chọn mô hình <code>gpt-image-2</code> và gửi yêu cầu vẽ tranh.</li>
              </ol>
            </CardContent>
          </Card>

          {/* One API / New API */}
          <Card className="border-stone-200 bg-white/80">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base text-stone-900">One API / New API</CardTitle>
                <Badge variant="outline" className="text-xs font-normal">API Gateway</Badge>
              </div>
              <CardDescription>Cấu hình kênh chuyển tiếp trung gian</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-xs text-stone-600">
              <ol className="list-decimal space-y-2 pl-4">
                <li>Đăng nhập bảng điều khiển One API / New API → mục <strong>Kênh (Channels)</strong>.</li>
                <li>Bấm <strong>Thêm kênh mới</strong>, chọn loại: <code>OpenAI</code>.</li>
                <li>Tại <strong>Base URL</strong>: Điền <code>{baseUrl.replace(/\/v1$/, "")}</code></li>
                <li>Tại <strong>Khóa (Key)</strong>: Điền khóa API của bạn.</li>
                <li>Tại <strong>Danh sách mô hình</strong>: Thêm <code>gpt-image-2,codex-gpt-image-2,auto</code></li>
                <li>Lưu kênh và tiến hành kiểm tra kết nối.</li>
              </ol>
            </CardContent>
          </Card>

          {/* Dify & Other Clients */}
          <Card className="border-stone-200 bg-white/80">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base text-stone-900">Dify / Chatbox / LobeHub</CardTitle>
                <Badge variant="outline" className="text-xs font-normal">Universal</Badge>
              </div>
              <CardDescription>Tất cả các nền tảng tương thích chuẩn OpenAI</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-xs text-stone-600">
              <p>
                Hệ thống tuân thủ hoàn toàn đặc tả OpenAI API. Bạn có thể thêm dưới dạng nhà cung cấp tùy chỉnh (Custom Provider):
              </p>
              <ul className="list-disc space-y-1.5 pl-4">
                <li><strong>Protocol:</strong> OpenAI Compatible</li>
                <li><strong>Endpoint / Base URL:</strong> <code>{baseUrl}</code></li>
                <li><strong>API Key:</strong> Khóa của bạn</li>
                <li><strong>Model Name:</strong> <code>gpt-image-2</code></li>
              </ul>
            </CardContent>
          </Card>
        </div>
      )}

      {/* TAB CONTENT: API EXAMPLES */}
      {activeTab === "api" && (
        <div className="space-y-6">
          <Card className="border-stone-200 bg-white/80">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base text-stone-900">1. Tạo ảnh mới (Text-to-Image)</CardTitle>
                  <CardDescription className="font-mono text-xs">POST /v1/images/generations</CardDescription>
                </div>
                <Badge className="bg-emerald-600 text-white hover:bg-emerald-700">Tương thích OpenAI</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-xs text-stone-600">
                Giao diện tạo hình ảnh mới từ câu lệnh mô tả văn bản (Prompt). Hỗ trợ trả về định dạng Base64 hoặc URL.
              </p>
              <div className="space-y-2">
                <div className="text-xs font-semibold text-stone-700">Ví dụ cURL:</div>
                <CodeBlock code={curlGenCode} language="bash" />
              </div>

              <div className="grid grid-cols-1 gap-4 pt-2 md:grid-cols-2">
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-stone-700">Ví dụ Python (openai SDK):</div>
                  <CodeBlock code={pythonCode} language="python" />
                </div>
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-stone-700">Ví dụ JavaScript / TypeScript:</div>
                  <CodeBlock code={jsCode} language="typescript" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-stone-200 bg-white/80">
            <CardHeader>
              <div>
                <CardTitle className="text-base text-stone-900">2. Chỉnh sửa ảnh theo ảnh tham chiếu (Image-to-Image)</CardTitle>
                <CardDescription className="font-mono text-xs">POST /v1/images/edits</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-xs text-stone-600">
                Gửi ảnh gốc kèm câu lệnh để biến đổi phong cách, thêm bớt chi tiết hoặc chỉnh sửa theo ý muốn qua định dạng <code>multipart/form-data</code>.
              </p>
              <div className="space-y-2">
                <div className="text-xs font-semibold text-stone-700">Ví dụ cURL:</div>
                <CodeBlock code={curlEditCode} language="bash" />
              </div>
            </CardContent>
          </Card>

          <Card className="border-stone-200 bg-white/80">
            <CardHeader>
              <div>
                <CardTitle className="text-base text-stone-900">3. Tạo ảnh qua Chat Completions</CardTitle>
                <CardDescription className="font-mono text-xs">POST /v1/chat/completions</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-xs text-stone-600">
                Dành cho các ứng dụng chỉ hỗ trợ giao diện hội thoại Chat nhưng muốn tạo ảnh trực tiếp trong luồng hội thoại.
              </p>
              <div className="space-y-2">
                <div className="text-xs font-semibold text-stone-700">Ví dụ cURL:</div>
                <CodeBlock code={curlChatCode} language="bash" />
              </div>
            </CardContent>
          </Card>

          <Card className="border-stone-200 bg-white/80">
            <CardHeader>
              <div>
                <CardTitle className="text-base text-stone-900">4. Lấy danh sách mô hình (Models)</CardTitle>
                <CardDescription className="font-mono text-xs">GET /v1/models</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <CodeBlock
                code={`curl ${baseUrl}/models -H "Authorization: Bearer <API_KEY_CUA_BAN>"`}
                language="bash"
              />
            </CardContent>
          </Card>
        </div>
      )}

      {/* TAB CONTENT: MODELS */}
      {activeTab === "models" && (
        <Card className="border-stone-200 bg-white/80">
          <CardHeader>
            <CardTitle className="text-lg text-stone-900">Danh sách Model hỗ trợ</CardTitle>
            <CardDescription>
              Chi tiết các model tạo ảnh và định tuyến khả dụng trong hệ thống
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-stone-200 text-stone-500">
                    <th className="pb-3 font-semibold">Tên Model</th>
                    <th className="pb-3 font-semibold">Loại tài khoản</th>
                    <th className="pb-3 font-semibold">Mô tả & Ứng dụng</th>
                    <th className="pb-3 font-semibold">Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 text-stone-700">
                  <tr>
                    <td className="py-3 font-mono font-bold text-stone-900">gpt-image-2</td>
                    <td className="py-3">Tất cả (Free, Plus, Team, Pro)</td>
                    <td className="py-3">Model tạo ảnh chính chất lượng cao nhất của ChatGPT, hỗ trợ tạo ảnh mới và chỉnh sửa ảnh.</td>
                    <td className="py-3"><Badge className="bg-emerald-600 text-white">Khuyên dùng</Badge></td>
                  </tr>
                  <tr>
                    <td className="py-3 font-mono font-bold text-stone-900">codex-gpt-image-2</td>
                    <td className="py-3">Plus / Team / Pro</td>
                    <td className="py-3">Kênh tạo ảnh qua endpoint Codex của ChatGPT, giúp nhân đôi hạn mức tạo ảnh song song trên cùng tài khoản.</td>
                    <td className="py-3"><Badge variant="outline">Mở rộng</Badge></td>
                  </tr>
                  <tr>
                    <td className="py-3 font-mono font-bold text-stone-900">auto</td>
                    <td className="py-3">Tất cả</td>
                    <td className="py-3">Tự động chọn model tối ưu dựa trên lượng tài khoản rảnh rỗi và loại gói tài khoản hiện có trong hệ thống.</td>
                    <td className="py-3"><Badge variant="outline">Tự động</Badge></td>
                  </tr>
                  <tr>
                    <td className="py-3 font-mono font-bold text-stone-900">gpt-5 / gpt-5-mini</td>
                    <td className="py-3">Tất cả</td>
                    <td className="py-3">Hỗ trợ giao diện gọi công cụ và hội thoại tương thích ngược.</td>
                    <td className="py-3"><Badge variant="secondary">Phụ trợ</Badge></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* TAB CONTENT: ADMIN MANAGEMENT */}
      {activeTab === "admin" && session.role === "admin" && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <Card className="border-stone-200 bg-white/80">
            <CardHeader>
              <CardTitle className="text-base text-stone-900">4 Cách nhập tài khoản ChatGPT</CardTitle>
              <CardDescription>Thêm tài khoản vào nhóm phân phối trong mục Quản lý tài khoản</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-xs text-stone-600">
              <ul className="list-disc space-y-2 pl-4">
                <li>
                  <strong>Nhập Access Token trực tiếp:</strong> Lấy chuỗi <code>accessToken</code> sau khi đăng nhập ChatGPT tại đường dẫn <code>https://chatgpt.com/api/auth/session</code>.
                </li>
                <li>
                  <strong>Nhập Session JSON:</strong> Dán hoặc tải file JSON phiên làm việc (Session) của trình duyệt.
                </li>
                <li>
                  <strong>Đồng bộ qua CPA Pool:</strong> Kết nối tới máy chủ CPA Pool từ xa để tự động tải danh sách tài khoản theo chu kỳ.
                </li>
                <li>
                  <strong>Đồng bộ qua Sub2API:</strong> Kết nối qua máy chủ Sub2API OAuth để đồng bộ tài khoản có sẵn.
                </li>
              </ul>
            </CardContent>
          </Card>

          <Card className="border-stone-200 bg-white/80">
            <CardHeader>
              <CardTitle className="text-base text-stone-900">Cơ chế bảo vệ & Quản lý thông minh</CardTitle>
              <CardDescription>Tự động xử lý sự cố giúp API luôn hoạt động 24/7</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-xs text-stone-600">
              <ul className="list-disc space-y-2 pl-4">
                <li>
                  <strong>Tự động cách ly tài khoản giới hạn (Rate-Limit):</strong> Khi tài khoản đạt hạn mức của OpenAI, hệ thống tạm thời đưa tài khoản vào trạng thái chờ hồi phục và định kỳ kiểm tra lại.
                </li>
                <li>
                  <strong>Tự động loại bỏ Token hỏng:</strong> Khi phát hiện tài khoản bị đăng xuất hoặc Token hết hạn, hệ thống tự động loại bỏ để không làm ảnh hưởng các request sau.
                </li>
                <li>
                  <strong>Hỗ trợ Proxy toàn cục:</strong> Cấu hình HTTP/HTTPS/SOCKS5 trong mục <strong>Cài đặt → Cài đặt Proxy</strong> để tránh rủi ro chặn IP từ OpenAI.
                </li>
              </ul>
            </CardContent>
          </Card>
        </div>
      )}

      {/* TAB CONTENT: FAQ */}
      {activeTab === "faq" && (
        <div className="space-y-4">
          <Card className="border-stone-200 bg-white/80">
            <CardHeader className="pb-3">
              <CardTitle className="text-base text-stone-900">1. Lỗi 401 Unauthorized khi gọi API?</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-stone-600">
              Nguyên nhân do bạn chưa truyền Header <code>Authorization: Bearer &lt;API_KEY&gt;</code> hoặc mã API Key không chính xác. Hãy kiểm tra lại API Key đã được cấp trong mục Cài đặt hoặc liên hệ quản trị viên.
            </CardContent>
          </Card>

          <Card className="border-stone-200 bg-white/80">
            <CardHeader className="pb-3">
              <CardTitle className="text-base text-stone-900">2. Lỗi 429 Too Many Requests (Hết hạn mức)?</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-stone-600">
              Toàn bộ tài khoản ChatGPT hiện có trong hệ thống đang bị giới hạn tần suất tạm thời từ OpenAI. Bạn có thể thêm thêm tài khoản mới vào nhóm hoặc chờ vài phút để các tài khoản tự động hồi phục hạn mức.
            </CardContent>
          </Card>

          <Card className="border-stone-200 bg-white/80">
            <CardHeader className="pb-3">
              <CardTitle className="text-base text-stone-900">3. Thời gian tạo một bức ảnh là bao lâu?</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-stone-600">
              Thời gian thông thường dao động từ 10 - 25 giây tùy thuộc vào độ phức tạp của câu lệnh prompt và độ tải của máy chủ OpenAI tại thời điểm đó.
            </CardContent>
          </Card>

          <Card className="border-stone-200 bg-white/80">
            <CardHeader className="pb-3">
              <CardTitle className="text-base text-stone-900">4. Định dạng ảnh trả về là gì?</CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-stone-600">
              Mặc định API trả về chuỗi <code>b64_json</code> (chuỗi Base64 chuẩn của ảnh) hoặc URL tạm thời lưu trên bộ nhớ đệm nếu bạn cấu hình lưu trữ R2 / Local.
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
