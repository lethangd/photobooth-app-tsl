<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from "vue";

import { KIOSK, getJson, sendJson } from "../api";
import { errorText, notify } from "../state";

/* The subset of the app configuration the kiosk owner changes day to day. */
interface Form {
  prices: Record<number, number>;
  retake_price: number;
  retake_max_shots: number;
  capture_countdown_seconds: number;
  payment_timeout_seconds: number;
  final_preview_timeout_seconds: number;
  qr_download_seconds: number;
  thank_you_seconds: number;
  digital_delivery_default_enabled: boolean;
  sound_enabled: boolean;
  reduce_motion: boolean;
  browser_camera_fallback: boolean;
  digital_delivery_retention_days: number;
  bank_bin: string;
  bank_account_number: string;
  bank_account_name: string;
  payment_qr_expiry_seconds: number;
  vouchers: Voucher[];
  print_enabled: boolean;
  extra_copy_price: number;
  max_print_copies: number;
  loyalty_enabled: boolean;
  loyalty_stamps_for_reward: number;
  support_hotline: string;
  social_handle: string;
  fx_foil_sweep: boolean;
  fx_holo_flow: boolean;
  fx_glow_breathe: boolean;
  fx_film_grain: boolean;
  fx_light_leak: boolean;
  fx_parallax: boolean;
}

interface Voucher {
  code: string;
  discount_amount: number;
  discount_percent: number;
  max_uses: number;
  valid_until: string;
  enabled: boolean;
}

/* Admin password and staff PIN are kept in .env on the kiosk, never in config.json. */
interface Security {
  admin_password_default: boolean;
  staff_pin_default: boolean;
  secrets_file: string;
  sepay: "token" | "webhook" | null;
}

/* NAPAS BINs of the banks most shops use (VietQR). */
const BANKS = [
  { bin: "970436", name: "Vietcombank" },
  { bin: "970422", name: "MB Bank" },
  { bin: "970407", name: "Techcombank" },
  { bin: "970415", name: "VietinBank" },
  { bin: "970418", name: "BIDV" },
  { bin: "970405", name: "Agribank" },
  { bin: "970416", name: "ACB" },
  { bin: "970423", name: "TPBank" },
  { bin: "970432", name: "VPBank" },
  { bin: "970403", name: "Sacombank" },
  { bin: "970448", name: "OCB" },
  { bin: "970454", name: "Viet Capital Bank" },
  { bin: "963388", name: "Timo" },
  { bin: "970441", name: "VIB" },
  { bin: "970443", name: "SHB" },
  { bin: "970437", name: "HDBank" },
];

type AppConfig = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const LABELS: Record<string, string> = {
  prices: "giá gói",
  retake_price: "giá chụp lại",
  retake_max_shots: "số lần chụp lại",
  capture_countdown_seconds: "thời gian đếm ngược",
  payment_timeout_seconds: "thời gian chờ xác nhận",
  final_preview_timeout_seconds: "thời gian tự in",
  qr_download_seconds: "thời gian hiện QR",
  thank_you_seconds: "màn cảm ơn",
  digital_delivery_default_enabled: "ảnh số mặc định",
  sound_enabled: "âm thanh",
  reduce_motion: "giảm hiệu ứng",
  browser_camera_fallback: "webcam dự phòng",
  digital_delivery_retention_days: "số ngày giữ ảnh",
  bank_bin: "ngân hàng",
  bank_account_number: "số tài khoản",
  bank_account_name: "tên chủ tài khoản",
  payment_qr_expiry_seconds: "hạn mã QR",
  vouchers: "mã giảm giá",
  print_enabled: "máy in",
  extra_copy_price: "giá bản in thêm",
  max_print_copies: "số bản in tối đa",
  loyalty_enabled: "tích điểm",
  loyalty_stamps_for_reward: "số lần để được tặng",
  support_hotline: "hotline",
  social_handle: "trang mạng xã hội",
  fx_foil_sweep: "vệt foil",
  fx_holo_flow: "viền holo chảy",
  fx_glow_breathe: "quầng sáng thở",
  fx_film_grain: "hạt film",
  fx_light_leak: "vệt sáng film",
  fx_parallax: "chiều sâu màn chờ",
};

const TIMINGS = [
  {
    key: "capture_countdown_seconds",
    label: "Đếm ngược mỗi kiểu",
    min: 5,
    max: 20,
    help: "Thời gian khách tạo dáng trước mỗi lần chụp.",
  },
  {
    key: "payment_timeout_seconds",
    label: "Chờ nhân viên xác nhận",
    min: 30,
    max: 600,
    help: "Quá thời gian này, kiosk tự huỷ phiên và về màn chờ.",
  },
  {
    key: "final_preview_timeout_seconds",
    label: "Tự in sau khi xem kết quả",
    min: 10,
    max: 120,
    help: 'Khách không bấm "In ảnh" thì máy tự in.',
  },
  {
    key: "qr_download_seconds",
    label: "Hiện mã QR nhận ảnh",
    min: 3,
    max: 90,
    help: "Đủ lâu để khách mở camera điện thoại quét.",
  },
  {
    key: "thank_you_seconds",
    label: "Màn cảm ơn",
    min: 2,
    max: 30,
    help: "Sau đó kiosk tự quay về màn chờ.",
  },
] as const;

const EFFECTS = [
  {
    key: "fx_foil_sweep",
    label: "Vệt foil quét sáng",
    help: "Chạy qua nhãn holo và nút chính mỗi 4–6 giây.",
  },
  {
    key: "fx_holo_flow",
    label: "Viền holo chảy màu",
    help: "Màu cầu vồng trong viền và đường dưới thanh tiêu đề trôi chậm.",
  },
  {
    key: "fx_glow_breathe",
    label: "Quầng sáng thở",
    help: "Quầng sáng sau vật chính phồng nhẹ, loé lên khi bấm nút chính.",
  },
  { key: "fx_film_grain", label: "Hạt film chạy", help: "Lớp hạt như film thật. Tắt nếu máy kiosk bị giật." },
  {
    key: "fx_light_leak",
    label: "Vệt sáng film trôi",
    help: "Vệt sáng cam hồng trên ảnh mẫu dịch chậm dọc mép ảnh.",
  },
  {
    key: "fx_parallax",
    label: "Chiều sâu màn chờ",
    help: "Khung và người lơ lửng lệch nhau, người như nhô ra trước khung.",
  },
] as const;

const TOGGLES = [
  {
    key: "digital_delivery_default_enabled",
    label: "Bật sẵn ảnh số + video qua QR",
    help: "Khách vẫn có thể tắt khi chọn khung.",
  },
  {
    key: "sound_enabled",
    label: "Âm thanh giao diện",
    help: "Pop, whoosh, màn trập, chuông khi thanh toán xong.",
  },
  { key: "reduce_motion", label: "Giảm hiệu ứng", help: "Bật khi máy kiosk yếu và chuyển trang bị giật." },
  {
    key: "browser_camera_fallback",
    label: "Dùng webcam khi camera chính lỗi",
    help: "Tự chuyển sang camera của máy tính hoặc điện thoại.",
  },
] as const;

const config = ref<AppConfig | null>(null);
const original = ref<Form | null>(null);
const form = reactive<Form>({
  prices: {},
  retake_price: 0,
  retake_max_shots: 1,
  capture_countdown_seconds: 10,
  payment_timeout_seconds: 180,
  final_preview_timeout_seconds: 30,
  qr_download_seconds: 18,
  thank_you_seconds: 9,
  digital_delivery_default_enabled: true,
  sound_enabled: true,
  reduce_motion: false,
  browser_camera_fallback: true,
  digital_delivery_retention_days: 7,
  bank_bin: "",
  bank_account_number: "",
  bank_account_name: "",
  payment_qr_expiry_seconds: 300,
  vouchers: [],
  print_enabled: false,
  extra_copy_price: 15000,
  max_print_copies: 4,
  loyalty_enabled: true,
  loyalty_stamps_for_reward: 5,
  support_hotline: "",
  social_handle: "",
  fx_foil_sweep: true,
  fx_holo_flow: true,
  fx_glow_breathe: true,
  fx_film_grain: true,
  fx_light_leak: true,
  fx_parallax: true,
});
const saving = ref(false);

const security = ref<Security | null>(null);
const currentPassword = ref("");
const newPassword = ref("");
const newPin = ref("");
const securityBusy = ref("");
const pinInput = ref<HTMLInputElement | null>(null);

const pinValid = computed(() => /^[0-9]{4}$/.test(newPin.value));
const changed = computed(() => {
  if (!original.value) return [] as string[];
  return (Object.keys(LABELS) as (keyof Form)[])
    .filter((key) => JSON.stringify(form[key]) !== JSON.stringify(original.value![key]))
    .map((key) => LABELS[key]);
});
const passwordTooShort = computed(() => newPassword.value.length > 0 && newPassword.value.length < 6);

function fromConfig(cfg: AppConfig): Form {
  const fb = cfg.framebooth;
  const prices: Record<number, number> = {};
  for (const tier of fb.pricing as { slot_count: number; price: number }[])
    prices[tier.slot_count] = tier.price;
  return {
    prices,
    retake_price: fb.retake_price,
    retake_max_shots: fb.retake_max_shots,
    capture_countdown_seconds: fb.capture_countdown_seconds,
    payment_timeout_seconds: fb.payment_timeout_seconds,
    final_preview_timeout_seconds: fb.final_preview_timeout_seconds,
    qr_download_seconds: fb.qr_download_seconds,
    thank_you_seconds: fb.thank_you_seconds,
    digital_delivery_default_enabled: fb.digital_delivery_default_enabled,
    sound_enabled: fb.sound_enabled,
    reduce_motion: fb.reduce_motion,
    browser_camera_fallback: fb.browser_camera_fallback,
    digital_delivery_retention_days: fb.digital_delivery_retention_days,
    bank_bin: fb.bank_bin ?? "",
    bank_account_number: fb.bank_account_number ?? "",
    bank_account_name: fb.bank_account_name ?? "",
    payment_qr_expiry_seconds: fb.payment_qr_expiry_seconds ?? 300,
    vouchers: fb.vouchers ?? [],
    print_enabled: fb.print_enabled ?? false,
    extra_copy_price: fb.extra_copy_price ?? 15000,
    max_print_copies: fb.max_print_copies ?? 4,
    loyalty_enabled: fb.loyalty_enabled ?? true,
    loyalty_stamps_for_reward: fb.loyalty_stamps_for_reward ?? 5,
    support_hotline: fb.support_hotline ?? "",
    social_handle: fb.social_handle ?? "",
    fx_foil_sweep: fb.fx_foil_sweep ?? true,
    fx_holo_flow: fb.fx_holo_flow ?? true,
    fx_glow_breathe: fb.fx_glow_breathe ?? true,
    fx_film_grain: fb.fx_film_grain ?? true,
    fx_light_leak: fb.fx_light_leak ?? true,
    fx_parallax: fb.fx_parallax ?? true,
  };
}

function fill(cfg: AppConfig): void {
  config.value = cfg;
  const values = fromConfig(cfg);
  original.value = JSON.parse(JSON.stringify(values));
  Object.assign(form, JSON.parse(JSON.stringify(values)));
}

async function load(): Promise<void> {
  try {
    const [cfg, sec] = await Promise.all([
      getJson<AppConfig>("/api/admin/config/app"),
      getJson<Security>(`${KIOSK}/security`),
    ]);
    fill(cfg);
    security.value = sec;
  } catch (exc) {
    notify(errorText(exc), true);
  }
}

/** Money inputs show "70.000" and accept any digits typed. */
function priceText(value: number): string {
  return new Intl.NumberFormat("vi-VN").format(value);
}

function parsePrice(text: string): number {
  return Number(text.replace(/\D/g, "")) || 0;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Math.round(value) || min));
}

function addVoucher(): void {
  form.vouchers.push({
    code: "",
    discount_amount: 10000,
    discount_percent: 0,
    max_uses: 0,
    valid_until: "",
    enabled: true,
  });
}

const voucherProblem = computed(() =>
  form.vouchers.some((v) => !/^[A-Z0-9-]{3,20}$/.test(v.code))
    ? "Mã giảm giá cần 3–20 ký tự: chữ in hoa, số hoặc dấu -"
    : "",
);
const bankProblem = computed(() =>
  Boolean(form.bank_bin) !== Boolean(form.bank_account_number.trim())
    ? "Chọn ngân hàng và nhập số tài khoản (hoặc để trống cả hai)"
    : "",
);

function reset(): void {
  if (original.value) Object.assign(form, JSON.parse(JSON.stringify(original.value)));
}

async function focusPin(): Promise<void> {
  await nextTick();
  pinInput.value?.scrollIntoView({ behavior: "smooth", block: "center" });
  pinInput.value?.focus({ preventScroll: true });
}

async function changeSecret(kind: "admin-password" | "staff-pin"): Promise<void> {
  if (securityBusy.value) return;
  if (!currentPassword.value) return notify("Nhập mật khẩu admin hiện tại để xác nhận", true);
  if (kind === "staff-pin" && !pinValid.value) return notify("PIN nhân viên phải gồm đúng 4 chữ số", true);
  if (kind === "admin-password" && newPassword.value.length < 6)
    return notify("Mật khẩu admin cần ít nhất 6 ký tự", true);

  securityBusy.value = kind;
  try {
    security.value = await sendJson<Security>(`${KIOSK}/security/${kind}`, "POST", {
      current_password: currentPassword.value,
      new_value: kind === "staff-pin" ? newPin.value : newPassword.value,
    });
    notify(kind === "staff-pin" ? "Đã đổi PIN nhân viên" : "Đã đổi mật khẩu admin");
    currentPassword.value = "";
    newPassword.value = "";
    newPin.value = "";
  } catch (exc) {
    notify(errorText(exc), true);
  } finally {
    securityBusy.value = "";
  }
}

async function save(): Promise<void> {
  if (!config.value || saving.value || !changed.value.length) return;
  if (voucherProblem.value || bankProblem.value)
    return notify(voucherProblem.value || bankProblem.value, true);
  form.bank_account_name = form.bank_account_name.trim().toUpperCase();

  const next: AppConfig = JSON.parse(JSON.stringify(config.value));
  const fb = next.framebooth;
  fb.pricing = (fb.pricing as { slot_count: number; price: number }[]).map((tier) => ({
    ...tier,
    price: form.prices[tier.slot_count] ?? tier.price,
  }));
  for (const key of Object.keys(LABELS) as (keyof Form)[]) {
    if (key === "prices") continue;
    fb[key] = form[key];
  }

  saving.value = true;
  try {
    await sendJson("/api/admin/config/app", "PATCH", next);
    notify("Đã lưu, áp dụng từ phiên tiếp theo");
    await load();
  } catch (exc) {
    notify(errorText(exc), true);
  } finally {
    saving.value = false;
  }
}

onMounted(() => void load());
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 20px; padding-bottom: 90px">
    <header class="page-head">
      <div>
        <div class="kicker">Áp dụng ngay cho phiên tiếp theo</div>
        <h1 class="h1">Cài đặt kiosk</h1>
      </div>
      <a href="/classic#/admin/config" target="_blank" rel="noopener" class="btn-link">Cấu hình nâng cao ↗</a>
    </header>

    <div v-if="!config" class="empty loading">Đang tải cấu hình…</div>

    <section v-else class="grid" style="align-items: start">
      <div class="card">
        <h2 class="h2">Giá &amp; thanh toán</h2>
        <div class="three">
          <label v-for="(price, slots) in form.prices" :key="slots" class="field">
            Gói {{ slots }} ảnh
            <span class="input-wrap">
              <input
                inputmode="numeric"
                :value="priceText(price)"
                @change="form.prices[Number(slots)] = parsePrice(($event.target as HTMLInputElement).value)"
              />
              <span class="unit">đ</span>
            </span>
          </label>
        </div>
        <div class="two">
          <label class="field">
            Giá mỗi lần chụp lại
            <span class="input-wrap">
              <input
                inputmode="numeric"
                :value="priceText(form.retake_price)"
                @change="form.retake_price = parsePrice(($event.target as HTMLInputElement).value)"
              />
              <span class="unit">đ</span>
            </span>
          </label>
          <label class="field">
            Chụp lại tối đa
            <span class="input-wrap">
              <input
                v-model.number="form.retake_max_shots"
                type="number"
                min="1"
                max="10"
                @change="form.retake_max_shots = clamp(form.retake_max_shots, 1, 10)"
              />
              <span class="unit">lần</span>
            </span>
          </label>
        </div>
        <div class="pin-card">
          <div style="flex: 1 1 180px">
            <div style="font-weight: 800">PIN nhân viên</div>
            <div style="font-size: 13px; color: #c7ccd6">4 chữ số · đổi khi có người nghỉ việc</div>
          </div>
          <span class="pin-dots">••••</span>
          <button
            type="button"
            class="btn btn-sm"
            style="background: #fff; color: var(--ink); font-weight: 800"
            @click="focusPin"
          >
            Đổi PIN
          </button>
          <span
            v-if="security?.staff_pin_default"
            style="flex-basis: 100%; color: #ffb3bd; font-size: 13px; font-weight: 700"
            >Đang dùng PIN mặc định 1234.</span
          >
        </div>
      </div>

      <div class="card">
        <h2 class="h2">Thời gian</h2>
        <label v-for="item in TIMINGS" :key="item.key" class="timing">
          <span
            style="display: flex; justify-content: space-between; gap: 8px; font-weight: 700; font-size: 15px"
          >
            <span>{{ item.label }}</span
            ><span class="mono" style="color: var(--cobalt)">{{ form[item.key] }} giây</span>
          </span>
          <input v-model.number="form[item.key]" type="range" :min="item.min" :max="item.max" />
          <span class="muted" style="font-size: 13px">{{ item.help }}</span>
        </label>
      </div>

      <div class="card" style="gap: 0">
        <h2 class="h2" style="margin-bottom: 8px">Trải nghiệm khách</h2>
        <label v-for="item in TOGGLES" :key="item.key" class="toggle-row">
          <span style="flex: 1">
            <span style="display: block; font-weight: 700">{{ item.label }}</span>
            <span class="muted" style="display: block; font-size: 13px">{{ item.help }}</span>
          </span>
          <input v-model="form[item.key]" type="checkbox" class="switch" />
        </label>
        <label class="toggle-row" style="font-weight: 700">
          <span style="flex: 1">Giữ ảnh số trên cloud</span>
          <span class="input-wrap" style="height: 48px; width: 130px">
            <input
              v-model.number="form.digital_delivery_retention_days"
              type="number"
              min="1"
              max="90"
              style="text-align: right"
              @change="
                form.digital_delivery_retention_days = clamp(form.digital_delivery_retention_days, 1, 90)
              "
            />
            <span class="unit">ngày</span>
          </span>
        </label>
      </div>

      <div class="card" style="gap: 0">
        <h2 class="h2" style="margin-bottom: 8px">Hiệu ứng nền</h2>
        <label v-for="item in EFFECTS" :key="item.key" class="toggle-row">
          <span style="flex: 1">
            <span style="display: block; font-weight: 700">{{ item.label }}</span>
            <span class="muted" style="display: block; font-size: 13px">{{ item.help }}</span>
          </span>
          <input v-model="form[item.key]" type="checkbox" class="switch" />
        </label>
        <span class="muted" style="font-size: 13px; padding-top: 10px"
          >"Giảm hiệu ứng" ở trên tắt toàn bộ cùng lúc.</span
        >
      </div>

      <div class="card">
        <h2 class="h2">Chuyển khoản (VietQR)</h2>
        <div class="two">
          <label class="field">
            Ngân hàng
            <span class="input-wrap">
              <select v-model="form.bank_bin" style="font-weight: 600">
                <option value="">— Không dùng QR —</option>
                <option v-for="bank in BANKS" :key="bank.bin" :value="bank.bin">{{ bank.name }}</option>
              </select>
            </span>
          </label>
          <label class="field">
            Số tài khoản
            <span class="input-wrap">
              <input
                v-model.trim="form.bank_account_number"
                inputmode="numeric"
                placeholder="VD: 0123456789"
              />
            </span>
          </label>
        </div>
        <label class="field">
          Tên chủ tài khoản
          <span class="input-wrap">
            <input
              v-model="form.bank_account_name"
              placeholder="NGUYEN VAN A"
              style="text-transform: uppercase"
            />
          </span>
        </label>
        <label class="field">
          Mã QR hết hạn sau
          <span class="input-wrap" style="width: 180px">
            <input
              v-model.number="form.payment_qr_expiry_seconds"
              type="number"
              min="60"
              max="1800"
              step="60"
              @change="form.payment_qr_expiry_seconds = clamp(form.payment_qr_expiry_seconds, 60, 1800)"
            />
            <span class="unit">giây</span>
          </span>
        </label>
        <p v-if="bankProblem" class="alert warn" style="display: block; margin: 0; font-size: 14px">
          {{ bankProblem }}
        </p>
        <span class="muted" style="font-size: 13px; line-height: 1.5">
          <template v-if="security?.sepay"
            >Đã nối SePay ({{ security.sepay === "token" ? "API token" : "webhook" }}): tiền chuyển khoản được
            xác nhận tự động.</template
          >
          <template v-else
            >Chưa nối SePay: nhân viên xác nhận chuyển khoản bằng PIN. Thêm SEPAY_API_TOKEN vào file
            <span class="mono">.env</span> để máy tự xác nhận.</template
          >
        </span>
      </div>

      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px">
          <h2 class="h2">Mã giảm giá</h2>
          <button type="button" class="btn btn-ghost btn-sm" @click="addVoucher">+ Thêm mã</button>
        </div>
        <div v-if="!form.vouchers.length" class="empty">
          Chưa có mã nào. Mã quà khách quen vẫn được tạo tự động.
        </div>
        <div v-for="(voucher, index) in form.vouchers" :key="index" class="voucher-row">
          <span class="input-wrap" style="flex: 1 1 150px">
            <input
              v-model="voucher.code"
              aria-label="Mã"
              placeholder="TSL-HELLO"
              class="mono"
              @input="voucher.code = voucher.code.toUpperCase().replace(/[^A-Z0-9-]/g, '')"
            />
          </span>
          <span class="input-wrap" style="flex: 1 1 130px">
            <input
              v-if="!voucher.discount_percent"
              aria-label="Giảm (đồng)"
              inputmode="numeric"
              :value="priceText(voucher.discount_amount)"
              @change="voucher.discount_amount = parsePrice(($event.target as HTMLInputElement).value)"
            />
            <input
              v-else
              v-model.number="voucher.discount_percent"
              aria-label="Giảm (%)"
              type="number"
              min="1"
              max="100"
            />
            <button
              type="button"
              class="unit unit-toggle"
              :aria-label="voucher.discount_percent ? 'Đổi sang giảm theo đồng' : 'Đổi sang giảm theo %'"
              @click="voucher.discount_percent = voucher.discount_percent ? 0 : 10"
            >
              {{ voucher.discount_percent ? "%" : "đ" }}
            </button>
          </span>
          <span class="input-wrap" style="flex: 0 1 120px">
            <input v-model.number="voucher.max_uses" aria-label="Số lượt" type="number" min="0" />
            <span class="unit">lượt</span>
          </span>
          <span class="input-wrap" style="flex: 0 1 170px">
            <input v-model="voucher.valid_until" aria-label="Hạn dùng" type="date" />
          </span>
          <input v-model="voucher.enabled" type="checkbox" class="switch" aria-label="Đang dùng" />
          <button type="button" class="icon-btn" aria-label="Xoá mã" @click="form.vouchers.splice(index, 1)">
            ✕
          </button>
        </div>
        <span class="muted" style="font-size: 13px"
          >0 lượt = không giới hạn · để trống ngày = không hết hạn.</span
        >
        <p v-if="voucherProblem" class="alert warn" style="display: block; margin: 0; font-size: 14px">
          {{ voucherProblem }}
        </p>
      </div>

      <div class="card" style="gap: 0">
        <h2 class="h2" style="margin-bottom: 8px">In ảnh &amp; khách quen</h2>
        <label class="toggle-row">
          <span style="flex: 1">
            <span style="display: block; font-weight: 700">Gửi lệnh in tới máy in</span>
            <span class="muted" style="display: block; font-size: 13px"
              >Tắt khi thử máy chưa có máy in: kiosk chỉ chạy hiệu ứng in.</span
            >
          </span>
          <input v-model="form.print_enabled" type="checkbox" class="switch" />
        </label>
        <div class="two" style="padding: 12px 0; border-top: 1.5px solid var(--soft)">
          <label class="field">
            Giá mỗi bản in thêm
            <span class="input-wrap">
              <input
                inputmode="numeric"
                :value="priceText(form.extra_copy_price)"
                @change="form.extra_copy_price = parsePrice(($event.target as HTMLInputElement).value)"
              />
              <span class="unit">đ</span>
            </span>
          </label>
          <label class="field">
            In tối đa
            <span class="input-wrap">
              <input
                v-model.number="form.max_print_copies"
                type="number"
                min="1"
                max="10"
                @change="form.max_print_copies = clamp(form.max_print_copies, 1, 10)"
              />
              <span class="unit">bản</span>
            </span>
          </label>
        </div>
        <label class="toggle-row">
          <span style="flex: 1">
            <span style="display: block; font-weight: 700">Tích điểm khách quen</span>
            <span class="muted" style="display: block; font-size: 13px"
              >Khách nhập số điện thoại, đủ số lần thì được tặng một lần chụp.</span
            >
          </span>
          <input v-model="form.loyalty_enabled" type="checkbox" class="switch" />
        </label>
        <div class="two" style="padding: 12px 0; border-top: 1.5px solid var(--soft)">
          <label class="field">
            Tặng sau
            <span class="input-wrap">
              <input
                v-model.number="form.loyalty_stamps_for_reward"
                type="number"
                min="2"
                max="20"
                @change="form.loyalty_stamps_for_reward = clamp(form.loyalty_stamps_for_reward, 2, 20)"
              />
              <span class="unit">lần</span>
            </span>
          </label>
          <label class="field">
            Hotline khi máy lỗi
            <span class="input-wrap"
              ><input v-model.trim="form.support_hotline" placeholder="0909 123 456"
            /></span>
          </label>
        </div>
        <label class="field" style="padding-top: 12px; border-top: 1.5px solid var(--soft)">
          Trang mạng xã hội (in trên ảnh story)
          <span class="input-wrap"
            ><input v-model.trim="form.social_handle" placeholder="@tslphotobooth"
          /></span>
        </label>
      </div>

      <div class="card">
        <h2 class="h2">Bảo mật</h2>
        <p
          v-if="security?.admin_password_default"
          class="alert warn"
          style="display: block; margin: 0; font-size: 14px; line-height: 1.5"
        >
          Bạn vẫn đang dùng mật khẩu mặc định <strong>0000</strong>. Hãy đổi trước khi mở kiosk cho khách.
        </p>
        <label class="field">
          Mật khẩu admin hiện tại
          <span class="input-wrap">
            <input
              v-model="currentPassword"
              type="password"
              placeholder="Để xác nhận thay đổi"
              autocomplete="current-password"
              style="font-weight: 600"
            />
          </span>
        </label>
        <div class="secret-row">
          <label class="field">
            Mật khẩu admin mới
            <span class="input-wrap" :style="{ borderColor: passwordTooShort ? 'var(--red)' : undefined }">
              <input
                v-model="newPassword"
                type="password"
                placeholder="Ít nhất 6 ký tự"
                autocomplete="new-password"
                style="font-weight: 600"
              />
            </span>
          </label>
          <button
            type="button"
            class="btn btn-dark"
            :disabled="!!securityBusy || newPassword.length < 6 || !currentPassword"
            @click="changeSecret('admin-password')"
          >
            {{ securityBusy === "admin-password" ? "Đang đổi…" : "Đổi mật khẩu" }}
          </button>
        </div>
        <div class="secret-row">
          <label class="field">
            PIN nhân viên mới
            <span class="input-wrap" :style="{ borderColor: newPin && !pinValid ? 'var(--red)' : undefined }">
              <input
                ref="pinInput"
                v-model="newPin"
                inputmode="numeric"
                maxlength="4"
                placeholder="4 chữ số"
                autocomplete="off"
                style="font-weight: 700; letter-spacing: 0.3em"
                @input="newPin = newPin.replace(/\D/g, '').slice(0, 4)"
              />
            </span>
          </label>
          <button
            type="button"
            class="btn btn-dark"
            :disabled="!!securityBusy || !pinValid || !currentPassword"
            @click="changeSecret('staff-pin')"
          >
            {{ securityBusy === "staff-pin" ? "Đang đổi…" : "Đổi PIN" }}
          </button>
        </div>
        <span class="muted" style="font-size: 13px; line-height: 1.5"
          >Lưu trong file <span class="mono">.env</span> trên máy kiosk, không nằm trong config.json. Sửa trực
          tiếp trong file cũng có hiệu lực ngay.</span
        >
      </div>
    </section>

    <Transition name="toast">
      <div v-if="changed.length" class="save-bar" role="region" aria-label="Thay đổi chưa lưu">
        <span style="flex: 1 1 200px; font-weight: 700"
          >Có {{ changed.length }} thay đổi chưa lưu · {{ changed.join(", ") }}</span
        >
        <button
          type="button"
          class="btn"
          style="border: 1.5px solid #4b5263; background: transparent; color: #fff"
          @click="reset"
        >
          Huỷ
        </button>
        <button type="button" class="btn btn-primary" :disabled="saving" @click="save">
          {{ saving ? "Đang lưu…" : "Lưu thay đổi" }}
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.three {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
}
.two {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}
.pin-card {
  align-items: center;
  background: var(--ink);
  border-radius: 20px;
  color: var(--white);
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  padding: 16px;
}
.pin-dots {
  font-family: var(--display);
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.3em;
}
.secret-row {
  align-items: flex-end;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.secret-row .field {
  flex: 1 1 200px;
}
.timing {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.toggle-row {
  align-items: center;
  border-top: 1.5px solid var(--soft);
  cursor: pointer;
  display: flex;
  gap: 14px;
  padding: 12px 0;
}
.save-bar {
  align-items: center;
  background: var(--ink);
  border-radius: 999px;
  bottom: 20px;
  box-shadow: 0 18px 40px rgba(20, 22, 28, 0.3);
  color: var(--white);
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  left: calc(256px + clamp(16px, 3vw, 40px));
  padding: 12px 14px 12px 22px;
  position: fixed;
  right: clamp(16px, 3vw, 40px);
  z-index: 35;
}
@media (max-width: 860px) {
  .save-bar {
    border-radius: 22px;
    bottom: 84px;
    left: 12px;
    right: 12px;
  }
}
.input-wrap select {
  background: transparent;
  border: 0;
  flex: 1;
  font-size: 16px;
  min-width: 0;
}
.input-wrap select:focus {
  outline: none;
}
.voucher-row {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.voucher-row .input-wrap {
  height: 46px;
}
.unit-toggle {
  background: var(--soft);
  border: 0;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 800;
  min-width: 34px;
  padding: 6px 8px;
}
</style>
