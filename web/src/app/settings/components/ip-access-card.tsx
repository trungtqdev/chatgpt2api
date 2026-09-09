"use client";

import { useMemo, useState } from "react";
import { Globe, LoaderCircle, Plus, Save, Shield, ShieldAlert, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { useSettingsStore } from "../store";

export function IPAccessCard() {
  const config = useSettingsStore((state) => state.config);
  const saveConfig = useSettingsStore((state) => state.saveConfig);
  const isSavingConfig = useSettingsStore((state) => state.isSavingConfig);
  const setIpAccessMode = useSettingsStore((state) => state.setIpAccessMode);
  const setAllowedIps = useSettingsStore((state) => state.setAllowedIps);
  const setIpWhitelistBypassAdmin = useSettingsStore((state) => state.setIpWhitelistBypassAdmin);

  const mode = config?.ip_access_mode || "all";
  const allowedIps = useMemo(() => config?.allowed_ips || [], [config?.allowed_ips]);
  const bypassAdmin = config?.ip_whitelist_bypass_admin !== false;
  const clientIp = String(config?.client_ip || "").trim();

  const [textareaValue, setTextareaValue] = useState(() => allowedIps.join("\n"));

  // Keep local textarea in sync when store changes
  const currentIpsText = allowedIps.join("\n");
  const isWhitelist = mode === "whitelist";

  const handleTextareaChange = (value: string) => {
    setTextareaValue(value);
    const parsed = value
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
    setAllowedIps(parsed);
  };

  const handleAddCurrentIp = () => {
    if (!clientIp) {
      toast.error("Không xác định được địa chỉ IP hiện tại");
      return;
    }
    const currentList = textareaValue
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);

    if (currentList.includes(clientIp)) {
      toast.info("Địa chỉ IP hiện tại đã có trong danh sách");
      return;
    }

    const newList = [...currentList, clientIp];
    const newText = newList.join("\n");
    setTextareaValue(newText);
    setAllowedIps(newList);
    toast.success(`Đã thêm IP ${clientIp} vào danh sách`);
  };

  const handleSave = async () => {
    const success = await saveConfig();
    if (success) {
      toast.success("Đã lưu cấu hình kiểm soát truy cập IP thành công");
    }
  };

  return (
    <Card className="border-stone-200 bg-white/80 backdrop-blur-sm">
      <CardHeader>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CardTitle className="text-base text-stone-900 flex items-center gap-2">
                <Shield className="size-4 text-stone-700" />
                <span>Kiểm soát truy cập theo IP (IP Whitelist)</span>
              </CardTitle>
            </div>
            <CardDescription>
              Cấu hình cho phép tất cả các IP hoặc chỉ cho phép một số IP cụ thể được gọi API (/v1/*).
            </CardDescription>
          </div>
          <div>
            {isWhitelist ? (
              <Badge variant="outline" className="gap-1 border-amber-300 bg-amber-50 text-amber-800">
                <ShieldAlert className="size-3 text-amber-600" />
                <span>Giới hạn Whitelist ({allowedIps.length} IP)</span>
              </Badge>
            ) : (
              <Badge variant="outline" className="gap-1 border-emerald-300 bg-emerald-50 text-emerald-800">
                <ShieldCheck className="size-3 text-emerald-600" />
                <span>Cho phép tất cả IP</span>
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        {/* Mode Selector */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => setIpAccessMode("all")}
            className={`flex flex-col items-start gap-1 rounded-2xl border p-4 text-left transition ${
              !isWhitelist
                ? "border-stone-900 bg-stone-900/5 ring-1 ring-stone-900"
                : "border-stone-200 bg-white hover:border-stone-300"
            }`}
          >
            <div className="flex items-center gap-2 font-medium text-sm text-stone-900">
              <Globe className="size-4 text-stone-600" />
              <span>Tất cả IP (Cho phép tự do)</span>
            </div>
            <p className="text-xs text-stone-500 leading-relaxed">
              Mọi IP trên Internet đều có thể gửi yêu cầu gọi API nếu có API Key hợp lệ.
            </p>
          </button>

          <button
            type="button"
            onClick={() => setIpAccessMode("whitelist")}
            className={`flex flex-col items-start gap-1 rounded-2xl border p-4 text-left transition ${
              isWhitelist
                ? "border-stone-900 bg-stone-900/5 ring-1 ring-stone-900"
                : "border-stone-200 bg-white hover:border-stone-300"
            }`}
          >
            <div className="flex items-center gap-2 font-medium text-sm text-stone-900">
              <Shield className="size-4 text-amber-600" />
              <span>Chỉ các IP trong danh sách (Whitelist)</span>
            </div>
            <p className="text-xs text-stone-500 leading-relaxed">
              Chỉ các IP hoặc dải mạng (CIDR) được cấu hình mới có thể gọi API. Các IP khác sẽ bị từ chối 403.
            </p>
          </button>
        </div>

        {/* Whitelist Configuration Section */}
        {isWhitelist && (
          <div className="space-y-4 rounded-2xl border border-stone-200 bg-stone-50/50 p-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-stone-700">
                  Danh sách địa chỉ IP / Dải mạng được phép (CIDR)
                </label>
                {clientIp ? (
                  <div className="flex items-center gap-2 text-xs text-stone-600">
                    <span>IP hiện tại của bạn: <strong className="font-mono text-stone-900">{clientIp}</strong></span>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleAddCurrentIp}
                      className="h-7 gap-1 rounded-lg border-stone-300 bg-white px-2 text-[11px] text-stone-700 hover:bg-stone-100"
                    >
                      <Plus className="size-3" />
                      <span>Thêm IP này</span>
                    </Button>
                  </div>
                ) : null}
              </div>

              <Textarea
                value={textareaValue}
                onChange={(e) => handleTextareaChange(e.target.value)}
                placeholder={"Ví dụ:\n192.168.1.100\n14.232.0.0/16\n2001:db8::/32\n(Mỗi dòng một địa chỉ IP hoặc subnet CIDR)"}
                className="min-h-32 rounded-xl border-stone-200 bg-white font-mono text-xs shadow-none"
              />
              <p className="text-[11px] text-stone-500">
                Hỗ trợ cả IPv4, IPv6 đơn lẻ (ví dụ <code>1.2.3.4</code>) và dải mạng CIDR (ví dụ <code>14.232.0.0/16</code>). Hệ thống luôn tự động cho phép <code>127.0.0.1</code> (localhost).
              </p>
            </div>

            <div className="pt-2">
              <label className="flex items-center gap-2.5 text-xs text-stone-700">
                <Checkbox
                  checked={bypassAdmin}
                  onCheckedChange={(checked) => setIpWhitelistBypassAdmin(Boolean(checked))}
                />
                <span>
                  <strong>Cho phép Quản trị viên (Admin) gọi API từ mọi IP:</strong> Bỏ qua kiểm tra IP khi request sử dụng Auth Key của Quản trị viên để tránh tình trạng vô tình bị khóa ngoài khi đổi mạng.
                </span>
              </label>
            </div>
          </div>
        )}

        {/* Save Button */}
        <div className="flex justify-end pt-1">
          <Button
            type="button"
            className="h-9 gap-1.5 rounded-xl bg-stone-900 px-4 text-xs font-semibold text-white transition hover:bg-stone-800"
            onClick={() => void handleSave()}
            disabled={isSavingConfig}
          >
            {isSavingConfig ? <LoaderCircle className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
            <span>Lưu cấu hình IP</span>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
