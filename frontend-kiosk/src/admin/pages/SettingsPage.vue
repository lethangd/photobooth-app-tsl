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
}

/* Admin password and staff PIN are kept hashed in .env on the kiosk, never in config.json. */
interface Security {
  admin_password_default: boolean;
  staff_pin_default: boolean;
  secrets_file: string;
}

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
          >Lưu dạng mã băm trong file <span class="mono">.env</span> trên máy kiosk, không nằm trong
          config.json.</span
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
</style>
