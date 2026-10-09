<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import {
  KIOSK,
  downloadFile,
  getJson,
  sendJson,
  type DayStats,
  type SessionDetail,
  type SessionRow,
} from "../api";
import AIcon from "../components/AIcon.vue";
import { isoDay, money, sessionCode, shiftDay, time } from "../format";
import { errorText, notify } from "../state";
import { sessionStatus } from "../status";

type Filter = "all" | "printed" | "unprinted" | "retake";

const route = useRoute();
const today = isoDay();
const day = ref(today);
const rows = ref<SessionRow[]>([]);
const stats = ref<DayStats | null>(null);
const query = ref("");
const filter = ref<Filter>("all");
const shown = ref(20);
const selectedId = ref<string | null>(typeof route.query.id === "string" ? route.query.id : null);
const detail = ref<SessionDetail | null>(null);
const busy = ref(false);

const counts = computed(() => ({
  all: rows.value.length,
  printed: rows.value.filter((row) => row.printed_at).length,
  unprinted: rows.value.filter((row) => !row.printed_at).length,
  retake: rows.value.filter((row) => row.retake_shots > 0).length,
}));
const chips = computed(() => [
  { key: "all" as Filter, label: `Tất cả · ${counts.value.all}` },
  { key: "printed" as Filter, label: `Đã in · ${counts.value.printed}` },
  { key: "unprinted" as Filter, label: `Chưa in · ${counts.value.unprinted}` },
  { key: "retake" as Filter, label: `Có chụp lại · ${counts.value.retake}` },
]);
const filtered = computed(() => {
  const needle = query.value.trim().toLowerCase();
  return rows.value.filter((row) => {
    if (needle && !row.session_id.toLowerCase().includes(needle)) return false;
    if (filter.value === "printed") return Boolean(row.printed_at);
    if (filter.value === "unprinted") return !row.printed_at;
    if (filter.value === "retake") return row.retake_shots > 0;
    return true;
  });
});
const visible = computed(() => filtered.value.slice(0, shown.value));
const totals = computed(() => [
  { label: "Doanh thu", value: money(stats.value?.revenue ?? 0), hot: true },
  { label: "Số phiên", value: String(stats.value?.sessions ?? 0) },
  { label: "Đã in", value: String(stats.value?.printed ?? 0) },
  { label: "Chụp lại", value: money(stats.value?.retake_revenue ?? 0) },
  { label: "Có ảnh số", value: String(stats.value?.digital ?? 0) },
]);

const timeline = computed(() => {
  const session = detail.value;
  if (!session) return [];
  const steps: { label: string; time: string; color: string }[] = [];
  if (session.slot_count)
    steps.push({
      label: `Chọn gói ${session.slot_count} ảnh`,
      time: time(session.created_at, true),
      color: "var(--cobalt)",
    });
  for (const pin of session.pin_events) {
    const what = pin.purpose === "retake" ? "chụp lại" : `gói`;
    steps.push({
      label: pin.ok
        ? `Nhân viên xác nhận PIN ${what} · ${money(pin.amount)}`
        : pin.locked
          ? "Bàn phím PIN bị khoá"
          : "Nhập sai PIN",
      time: time(pin.created_at, true),
      color: pin.ok ? "var(--green)" : "var(--red)",
    });
  }
  if (session.printed_at)
    steps.push({ label: "In ảnh", time: time(session.printed_at, true), color: "var(--cobalt)" });
  if (session.cloud_url)
    steps.push({ label: "Tải lên ảnh số", time: time(session.printed_at, true), color: "var(--cobalt)" });
  return steps;
});

async function load(): Promise<void> {
  try {
    const [loadedRows, loadedStats] = await Promise.all([
      getJson<SessionRow[]>(`${KIOSK}/sessions?day=${day.value}&limit=1000`),
      getJson<DayStats>(`${KIOSK}/stats?day=${day.value}`),
    ]);
    rows.value = loadedRows;
    stats.value = loadedStats;
    if (selectedId.value && !loadedRows.some((row) => row.session_id === selectedId.value))
      selectedId.value = null;
    if (!selectedId.value && loadedRows[0]) selectedId.value = loadedRows[0].session_id;
  } catch (exc) {
    notify(errorText(exc), true);
  }
}

async function loadDetail(): Promise<void> {
  detail.value = null;
  if (!selectedId.value) return;
  try {
    detail.value = await getJson<SessionDetail>(`${KIOSK}/sessions/${encodeURIComponent(selectedId.value)}`);
  } catch (exc) {
    notify(errorText(exc), true);
  }
}

async function reprint(): Promise<void> {
  if (!detail.value || busy.value) return;
  busy.value = true;
  try {
    await sendJson(`${KIOSK}/sessions/${encodeURIComponent(detail.value.session_id)}/print`, "POST");
    notify(`Đã gửi lệnh in lại ${sessionCode(detail.value.session_id)}`);
  } catch (exc) {
    notify(errorText(exc), true);
  } finally {
    busy.value = false;
  }
}

async function exportCsv(): Promise<void> {
  try {
    await downloadFile(`${KIOSK}/sessions.csv?day=${day.value}`, `doanh-thu-${day.value}.csv`);
  } catch (exc) {
    notify(errorText(exc), true);
  }
}

watch(day, () => {
  shown.value = 20;
  selectedId.value = null;
  void load();
});
watch(selectedId, () => void loadDetail());
onMounted(async () => {
  await load();
  await loadDetail();
});
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 20px">
    <header class="page-head">
      <div>
        <div class="kicker">Doanh thu &amp; lịch sử</div>
        <h1 class="h1">Phiên &amp; doanh thu</h1>
      </div>
      <div class="actions">
        <button type="button" class="icon-btn" aria-label="Ngày trước" @click="day = shiftDay(day, -1)">
          <AIcon name="chevron-left" :stroke="2.6" />
        </button>
        <label class="date-field">
          <span class="kicker">Ngày</span>
          <input v-model="day" type="date" :max="today" />
        </label>
        <button
          type="button"
          class="icon-btn"
          aria-label="Ngày sau"
          :disabled="day >= today"
          @click="day = shiftDay(day, 1)"
        >
          <AIcon name="chevron-right" :stroke="2.6" />
        </button>
        <button type="button" class="btn btn-dark" :disabled="!rows.length" @click="exportCsv">
          <AIcon name="download" />Xuất Excel
        </button>
      </div>
    </header>

    <section class="kpis small" aria-label="Tổng trong ngày">
      <div v-for="item in totals" :key="item.label" class="kpi" :class="{ hot: item.hot }">
        <div class="kicker">{{ item.label }}</div>
        <div class="kpi-value">{{ item.value }}</div>
      </div>
    </section>

    <section class="split">
      <div class="card wide">
        <div class="actions">
          <label class="search">
            <AIcon name="search" :size="18" :stroke="2.2" />
            <span class="sr-only">Tìm mã phiên</span>
            <input v-model="query" type="search" placeholder="Tìm mã phiên, ví dụ 4821" />
          </label>
          <button
            v-for="chip in chips"
            :key="chip.key"
            type="button"
            class="chip"
            :class="{ on: filter === chip.key }"
            :aria-pressed="filter === chip.key"
            @click="filter = chip.key"
          >
            {{ chip.label }}
          </button>
        </div>
        <div v-if="!filtered.length" class="empty">
          Không có phiên nào {{ rows.length ? "khớp bộ lọc" : "trong ngày này" }}.
        </div>
        <div v-else class="table-wrap">
          <table class="table" style="min-width: 680px">
            <thead>
              <tr>
                <th>Giờ</th>
                <th>Mã phiên</th>
                <th>Gói</th>
                <th>Chụp lại</th>
                <th>Ảnh số</th>
                <th style="text-align: right">Tổng</th>
                <th>Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in visible"
                :key="row.session_id"
                class="clickable"
                :class="{ selected: row.session_id === selectedId }"
                tabindex="0"
                @click="selectedId = row.session_id"
                @keydown.enter="selectedId = row.session_id"
              >
                <td class="mono">{{ time(row.created_at) }}</td>
                <td style="font-weight: 800">{{ sessionCode(row.session_id) }}</td>
                <td>{{ row.slot_count ? `${row.slot_count} ảnh` : "—" }}</td>
                <td>{{ row.retake_shots ? `${row.retake_shots} lần` : "—" }}</td>
                <td>{{ row.digital === null ? "—" : row.digital ? "Có" : "Không" }}</td>
                <td class="num">{{ money(row.total) }}</td>
                <td>
                  <span class="pill" :class="sessionStatus(row).kind">{{ sessionStatus(row).label }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div
          v-if="filtered.length"
          style="display: flex; justify-content: space-between; align-items: center; font-size: 14px"
          class="muted"
        >
          <span>Hiển thị {{ visible.length }} / {{ filtered.length }} phiên</span>
          <button
            v-if="visible.length < filtered.length"
            type="button"
            class="btn btn-ghost btn-sm"
            @click="shown += 20"
          >
            Xem thêm
          </button>
        </div>
      </div>

      <aside
        class="card narrow"
        :aria-label="detail ? `Chi tiết phiên ${sessionCode(detail.session_id)}` : 'Chi tiết phiên'"
        :style="{
          borderColor: detail ? 'var(--cobalt)' : undefined,
          borderWidth: detail ? '2px' : undefined,
        }"
      >
        <div v-if="!detail" class="empty">Chọn một phiên để xem chi tiết.</div>
        <template v-else>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px">
            <div>
              <div class="kicker">Chi tiết phiên</div>
              <div style="font-family: var(--display); font-weight: 800; font-size: 26px; margin-top: 4px">
                {{ sessionCode(detail.session_id) }}
              </div>
            </div>
            <span class="pill" :class="sessionStatus(detail).kind">{{ sessionStatus(detail).label }}</span>
          </div>
          <div class="row-item">
            <a v-if="detail.media_url" :href="detail.media_url" target="_blank" rel="noopener" class="thumb">
              <img :src="detail.media_url" alt="Ảnh đã in" />
            </a>
            <div v-else class="thumb empty-thumb mono">Chưa in</div>
            <div style="display: flex; flex-direction: column; gap: 4px; font-size: 14px">
              <strong style="font-size: 16px">Gói {{ detail.slot_count || "?" }} ảnh</strong>
              <span class="muted">{{
                detail.digital ? "Có ảnh số qua QR" : detail.digital === false ? "Chỉ in ảnh" : "—"
              }}</span>
              <a
                v-if="detail.cloud_url"
                :href="detail.cloud_url"
                target="_blank"
                rel="noopener"
                style="font-weight: 700; text-decoration: none"
                >Mở trang tải ảnh ↗</a
              >
            </div>
          </div>
          <ol class="timeline">
            <li v-for="(step, index) in timeline" :key="index">
              <span class="tl-dot" :style="{ background: step.color }" />
              <span style="flex: 1; font-weight: 600">{{ step.label }}</span>
              <span class="mono muted" style="font-size: 12px">{{ step.time }}</span>
            </li>
          </ol>
          <div
            style="
              padding-top: 14px;
              border-top: 1.5px solid var(--soft);
              display: flex;
              flex-direction: column;
              gap: 8px;
              font-size: 15px;
            "
          >
            <div style="display: flex; justify-content: space-between">
              <span>Gói {{ detail.slot_count }} ảnh</span><span>{{ money(detail.package_price) }}</span>
            </div>
            <div v-if="detail.retake_shots" style="display: flex; justify-content: space-between">
              <span>Chụp lại {{ detail.retake_shots }} lần</span
              ><span>{{ money(detail.retake_amount) }}</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-weight: 800; font-size: 18px">
              <span>Tổng</span><span>{{ money(detail.total) }}</span>
            </div>
          </div>
          <div class="actions">
            <button
              type="button"
              class="btn btn-primary"
              style="flex: 1"
              :disabled="!detail.mediaitem_id || busy"
              @click="reprint"
            >
              <AIcon name="printer" />{{ busy ? "Đang gửi…" : "In lại" }}
            </button>
            <a
              v-if="detail.media_url"
              :href="detail.media_url"
              :download="`${detail.session_id}.jpg`"
              class="btn btn-ghost"
              style="flex: 1"
              ><AIcon name="download" />Tải ảnh về</a
            >
          </div>
        </template>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.thumb {
  align-items: center;
  background: var(--white);
  border-radius: 10px;
  display: flex;
  flex: none;
  height: 98px;
  justify-content: center;
  overflow: hidden;
  width: 74px;
}
.thumb img {
  height: 100%;
  object-fit: contain;
  width: 100%;
}
.empty-thumb {
  border: 1.5px dashed #9aa3b2;
  color: var(--muted);
  font-size: 11px;
}
.timeline {
  display: flex;
  flex-direction: column;
  gap: 14px;
  list-style: none;
  margin: 0;
  padding: 0;
}
.timeline li {
  align-items: flex-start;
  display: flex;
  gap: 12px;
}
.tl-dot {
  border-radius: 50%;
  flex: none;
  height: 14px;
  margin-top: 4px;
  width: 14px;
}
</style>
