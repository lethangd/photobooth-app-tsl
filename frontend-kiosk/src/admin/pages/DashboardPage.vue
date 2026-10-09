<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { KIOSK, getJson, type DayStats, type Overview, type SessionRow } from "../api";
import AIcon from "../components/AIcon.vue";
import {
  isoDay,
  longDate,
  money,
  percentChange,
  sessionCode,
  shortMoney,
  shortWeekday,
  dayMonth,
  time,
  bytes,
} from "../format";
import { errorText, notify } from "../state";
import { sessionStatus } from "../status";

const RANGES = [
  { days: 1, label: "Hôm nay" },
  { days: 7, label: "7 ngày" },
  { days: 30, label: "30 ngày" },
];

const range = ref(1);
const stats = ref<DayStats | null>(null);
const overview = ref<Overview | null>(null);
const recent = ref<SessionRow[]>([]);
const loading = ref(false);
const today = isoDay();

const rangeWord = computed(() => (range.value === 1 ? "hôm nay" : `${range.value} ngày`));
const change = computed(() =>
  stats.value ? percentChange(stats.value.revenue, stats.value.previous.revenue) : null,
);
const changeText = computed(() => {
  if (change.value === null)
    return range.value === 1 ? "Chưa có số liệu hôm qua để so sánh" : "Chưa có số liệu kỳ trước";
  const versus = range.value === 1 ? "hôm qua" : `${range.value} ngày trước đó`;
  return `${change.value >= 0 ? "▲" : "▼"} ${Math.abs(change.value)}% so với ${versus}`;
});
const chartDays = computed(() => (range.value === 30 ? 30 : 7));
const series = computed(() => (stats.value?.series ?? []).slice(-chartDays.value));
const maxRevenue = computed(() => Math.max(1, ...series.value.map((day) => day.revenue)));
const seriesTotal = computed(() =>
  series.value.reduce(
    (sum, day) => ({ revenue: sum.revenue + day.revenue, sessions: sum.sessions + day.sessions }),
    { revenue: 0, sessions: 0 },
  ),
);
const packages = computed(() => {
  const list = stats.value?.by_package ?? [];
  const max = Math.max(1, ...list.map((item) => item.sessions));
  const colors: Record<number, string> = { 2: "var(--mint)", 3: "var(--cobalt)", 4: "var(--peach)" };
  return [...list]
    .sort((a, b) => b.sessions - a.sessions)
    .map((item) => ({
      ...item,
      width: `${(item.sessions / max) * 100}%`,
      color: colors[item.slot_count] ?? "var(--lilac)",
    }));
});

const printer = computed(() => overview.value?.printer.kiosk_printer ?? null);
const alerts = computed(() => {
  const list: { level: "warn" | "error"; title: string; text: string; to: string }[] = [];
  const ov = overview.value;
  if (!ov) return list;
  if (!ov.printer.kiosk_printer) {
    list.push({
      level: "error",
      title: "Không tìm thấy máy in của kiosk",
      text: `Máy in "${ov.printer.configured_name || "chưa đặt"}" không có trên máy tính.`,
      to: "/devices",
    });
  } else if (
    ov.printer.kiosk_printer.severity === "error" ||
    ov.printer.kiosk_printer.severity === "warning"
  ) {
    list.push({
      level: ov.printer.kiosk_printer.severity === "error" ? "error" : "warn",
      title: `Máy in: ${ov.printer.kiosk_printer.summary}`,
      text: `${ov.printer.kiosk_printer.name} cần được kiểm tra trước khi khách in ảnh.`,
      to: "/devices",
    });
  }
  if (!ov.camera.running) {
    list.push({
      level: ov.camera.browser_fallback ? "warn" : "error",
      title: "Camera chính không phản hồi",
      text: ov.camera.browser_fallback
        ? "Kiosk đang dùng webcam dự phòng. Kiểm tra cáp và nguồn của máy ảnh."
        : "Khách sẽ không chụp được ảnh. Kiểm tra cáp và nguồn của máy ảnh.",
      to: "/devices",
    });
  }
  return list;
});

const devices = computed(() => {
  const ov = overview.value;
  if (!ov) return [];
  const level = (severity: string) =>
    severity === "ok" || severity === "info" ? "ok" : severity === "warning" ? "warn" : "err";
  return [
    {
      name: "Camera",
      detail: [ov.camera.description, ov.camera.backend].filter(Boolean).join(" · ") || "Chưa cấu hình",
      state: ov.camera.running ? "Hoạt động" : "Không phản hồi",
      level: ov.camera.running ? "ok" : "err",
    },
    {
      name: "Máy in",
      detail: printer.value ? `${printer.value.name} · ${printer.value.jobs} lệnh chờ` : "Chưa có máy in",
      state: printer.value ? printer.value.summary.split(" · ")[0] : "Không tìm thấy",
      level: printer.value ? level(printer.value.severity) : "err",
    },
    {
      name: "Lưu trữ ảnh số",
      detail: ov.cloud.available
        ? `Cloudflare R2 · ${bytes(ov.cloud.bytes)} / 10 GB`
        : ov.cloud.enabled
          ? "Chưa cấu hình R2"
          : "Đang tắt",
      state: ov.cloud.available ? "Đã kết nối" : ov.cloud.enabled ? "Chưa kết nối" : "Tắt",
      level: ov.cloud.available ? "ok" : ov.cloud.enabled ? "warn" : "off",
    },
    {
      name: "Webcam dự phòng",
      detail: "Camera của máy tính hoặc điện thoại",
      state: ov.camera.browser_fallback ? "Sẵn sàng" : "Đang tắt",
      level: ov.camera.browser_fallback ? "ok" : "off",
    },
  ];
});

async function load(): Promise<void> {
  loading.value = true;
  try {
    const [loadedStats, loadedOverview, loadedRecent] = await Promise.all([
      getJson<DayStats>(`${KIOSK}/stats?day=${today}&range_days=${range.value}&days=${chartDays.value}`),
      getJson<Overview>(`${KIOSK}/overview`),
      getJson<SessionRow[]>(`${KIOSK}/sessions?day=${today}&limit=5`),
    ]);
    stats.value = loadedStats;
    overview.value = loadedOverview;
    recent.value = loadedRecent;
  } catch (exc) {
    notify(errorText(exc), true);
  } finally {
    loading.value = false;
  }
}

watch(range, () => void load());
onMounted(() => void load());
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 22px">
    <header class="page-head">
      <div>
        <div class="kicker">{{ longDate(today) }}</div>
        <h1 class="h1">Tổng quan</h1>
      </div>
      <div class="actions">
        <div class="seg" role="group" aria-label="Khoảng thời gian">
          <button
            v-for="item in RANGES"
            :key="item.days"
            type="button"
            :class="{ on: range === item.days }"
            :aria-pressed="range === item.days"
            @click="range = item.days"
          >
            {{ item.label }}
          </button>
        </div>
        <button type="button" class="icon-btn" aria-label="Làm mới" :class="{ loading }" @click="load">
          <AIcon name="refresh" :stroke="2.2" />
        </button>
      </div>
    </header>

    <router-link
      v-for="alert in alerts"
      :key="alert.title"
      :to="alert.to"
      class="alert"
      :class="alert.level"
      role="alert"
      style="color: inherit; text-decoration: none"
    >
      <span class="alert-icon">!</span>
      <span class="alert-body">
        <strong>{{ alert.title }}</strong>
        <span>{{ alert.text }}</span>
      </span>
      <span class="btn-link">Xem chi tiết →</span>
    </router-link>

    <section class="kpis" aria-label="Số liệu">
      <div class="kpi hot">
        <div class="kicker">Doanh thu {{ rangeWord }}</div>
        <div class="kpi-value">{{ money(stats?.revenue ?? 0) }}</div>
        <div class="kpi-note">{{ changeText }}</div>
      </div>
      <div class="kpi">
        <div class="kicker">Số phiên</div>
        <div class="kpi-value">{{ stats?.sessions ?? 0 }}</div>
        <div class="kpi-note muted">
          {{ stats?.printed ?? 0 }} đã in · {{ stats?.digital ?? 0 }} có ảnh số
        </div>
      </div>
      <div class="kpi">
        <div class="kicker">Ảnh đã in</div>
        <div class="kpi-value">{{ stats?.printed ?? 0 }}</div>
        <div class="kpi-note muted">Trung bình {{ money(stats?.average_ticket ?? 0) }} / phiên</div>
      </div>
      <div class="kpi">
        <div class="kicker">Tiền chụp lại</div>
        <div class="kpi-value">{{ money(stats?.retake_revenue ?? 0) }}</div>
        <div class="kpi-note muted">{{ stats?.retake_shots ?? 0 }} lần chụp thêm</div>
      </div>
    </section>

    <section class="grid">
      <div class="card span-2">
        <div class="card-head">
          <h2 class="h2">Doanh thu {{ chartDays }} ngày</h2>
          <span class="muted" style="font-size: 14px"
            >Tổng {{ money(seriesTotal.revenue) }} · {{ seriesTotal.sessions }} phiên</span
          >
        </div>
        <div class="bars" :style="{ gap: chartDays > 7 ? '4px' : '14px' }">
          <div
            v-for="(day, index) in series"
            :key="day.day"
            class="bar-col"
            :title="`${dayMonth(day.day)}: ${money(day.revenue)} · ${day.sessions} phiên`"
          >
            <span v-if="chartDays <= 7" class="bar-value">{{ shortMoney(day.revenue) }}</span>
            <div
              class="bar"
              :class="{ hot: index === series.length - 1 }"
              :style="{ height: `${(day.revenue / maxRevenue) * 160}px` }"
            />
            <span class="bar-label">{{
              chartDays <= 7 ? shortWeekday(day.day) : index % 5 === 4 ? dayMonth(day.day) : ""
            }}</span>
          </div>
        </div>
      </div>
      <div class="card">
        <h2 class="h2">Gói bán {{ rangeWord }}</h2>
        <div v-if="!packages.length" class="empty">Chưa có phiên nào.</div>
        <div
          v-for="item in packages"
          :key="item.slot_count"
          style="display: flex; flex-direction: column; gap: 8px"
        >
          <div style="display: flex; justify-content: space-between; font-weight: 700">
            <span>{{ item.slot_count }} ảnh</span><span>{{ item.sessions }} phiên</span>
          </div>
          <div class="meter"><i :style="{ width: item.width, background: item.color }" /></div>
        </div>
        <div
          style="
            margin-top: auto;
            padding-top: 12px;
            border-top: 1.5px solid var(--soft);
            display: flex;
            justify-content: space-between;
            font-size: 14px;
          "
        >
          <span class="muted">Trung bình mỗi phiên</span
          ><strong>{{ money(stats?.average_ticket ?? 0) }}</strong>
        </div>
      </div>
    </section>

    <section class="grid">
      <div class="card">
        <div class="card-head">
          <h2 class="h2">Thiết bị</h2>
          <router-link to="/devices">Chi tiết</router-link>
        </div>
        <div v-for="device in devices" :key="device.name" class="row-item">
          <span class="dot" :class="device.level" />
          <div class="grow">
            <div style="font-weight: 700">{{ device.name }}</div>
            <div class="sub">{{ device.detail }}</div>
          </div>
          <span class="pill" :class="device.level === 'off' ? 'muted' : device.level">{{
            device.state
          }}</span>
        </div>
      </div>
      <div class="card span-2">
        <div class="card-head">
          <h2 class="h2">Phiên gần đây</h2>
          <router-link to="/sessions">Xem tất cả</router-link>
        </div>
        <div v-if="!recent.length" class="empty">
          Hôm nay chưa có phiên nào. Doanh thu được ghi khi nhân viên nhập PIN xác nhận thanh toán.
        </div>
        <div v-else class="table-wrap">
          <table class="table" style="min-width: 520px">
            <thead>
              <tr>
                <th>Giờ</th>
                <th>Mã phiên</th>
                <th>Gói</th>
                <th>Chụp lại</th>
                <th style="text-align: right">Tổng</th>
                <th>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in recent"
                :key="row.session_id"
                class="clickable"
                @click="$router.push({ path: '/sessions', query: { id: row.session_id } })"
              >
                <td class="mono">{{ time(row.created_at) }}</td>
                <td style="font-weight: 700">{{ sessionCode(row.session_id) }}</td>
                <td>{{ row.slot_count ? `${row.slot_count} ảnh` : "—" }}</td>
                <td>{{ row.retake_shots ? `${row.retake_shots} lần` : "—" }}</td>
                <td class="num">{{ money(row.total) }}</td>
                <td>
                  <span class="pill" :class="sessionStatus(row).kind">{{ sessionStatus(row).label }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</template>
