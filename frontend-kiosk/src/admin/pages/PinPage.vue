<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { KIOSK, getJson, type DayStats, type PinEvent } from "../api";
import AIcon from "../components/AIcon.vue";
import { isoDay, money, sessionCode, shiftDay, time } from "../format";
import { errorText, notify } from "../state";

type Filter = "all" | "ok" | "bad" | "locked";

const today = isoDay();
const day = ref(today);
const events = ref<PinEvent[]>([]);
const stats = ref<DayStats | null>(null);
const filter = ref<Filter>("all");

const okEvents = computed(() => events.value.filter((event) => event.ok));
const badEvents = computed(() => events.value.filter((event) => !event.ok));
const lockedEvents = computed(() => events.value.filter((event) => event.locked));
const confirmed = computed(() => okEvents.value.reduce((sum, event) => sum + event.amount, 0));
const packageCount = computed(() => okEvents.value.filter((event) => event.purpose === "package").length);

const totals = computed(() => [
  {
    label: "Xác nhận đúng",
    value: String(okEvents.value.length),
    note: `${packageCount.value} gói · ${okEvents.value.length - packageCount.value} chụp lại`,
    hot: true,
  },
  {
    label: "Nhập sai",
    value: String(badEvents.value.length),
    note: lockedEvents.value.length ? `${lockedEvents.value.length} lần bị khoá` : "Không có lần khoá",
  },
  {
    label: "Tiền đã xác nhận",
    value: money(confirmed.value),
    note:
      stats.value && confirmed.value === stats.value.revenue
        ? "Khớp doanh thu ngày"
        : `Doanh thu ngày ${money(stats.value?.revenue ?? 0)}`,
  },
  {
    label: "Lần khoá bàn phím",
    value: String(lockedEvents.value.length),
    note: "Khoá 30 giây sau 5 lần sai",
  },
]);
const chips = computed(() => [
  { key: "all" as Filter, label: `Tất cả · ${events.value.length}` },
  { key: "ok" as Filter, label: `Đúng · ${okEvents.value.length}` },
  { key: "bad" as Filter, label: `Sai · ${badEvents.value.length}` },
  { key: "locked" as Filter, label: `Bị khoá · ${lockedEvents.value.length}` },
]);
const visible = computed(() => {
  if (filter.value === "ok") return okEvents.value;
  if (filter.value === "bad") return badEvents.value;
  if (filter.value === "locked") return lockedEvents.value;
  return events.value;
});
const latestFailure = computed(() => badEvents.value[0] ?? null);

function title(event: PinEvent): string {
  if (event.locked) return "Bàn phím PIN bị khoá";
  if (!event.ok) return "Nhập sai PIN";
  return event.purpose === "retake" ? "Xác nhận chụp lại" : "Xác nhận gói chụp";
}

function detail(event: PinEvent): string {
  return `${sessionCode(event.session_id)} · ${event.purpose === "retake" ? "chụp lại" : "gói"}`;
}

async function load(): Promise<void> {
  try {
    const [loadedEvents, loadedStats] = await Promise.all([
      getJson<PinEvent[]>(`${KIOSK}/pin-events?day=${day.value}&limit=1000`),
      getJson<DayStats>(`${KIOSK}/stats?day=${day.value}`),
    ]);
    events.value = loadedEvents;
    stats.value = loadedStats;
  } catch (exc) {
    notify(errorText(exc), true);
  }
}

watch(day, () => void load());
onMounted(() => void load());
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 20px">
    <header class="page-head">
      <div>
        <div class="kicker">Xác nhận thanh toán của nhân viên</div>
        <h1 class="h1">Nhật ký PIN</h1>
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
      </div>
    </header>

    <section class="kpis small" aria-label="Tóm tắt">
      <div v-for="item in totals" :key="item.label" class="kpi" :class="{ hot: item.hot }">
        <div class="kicker">{{ item.label }}</div>
        <div class="kpi-value">{{ item.value }}</div>
        <div class="kpi-note">{{ item.note }}</div>
      </div>
    </section>

    <section class="split">
      <div class="card wide">
        <div class="actions">
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
        <div v-if="!visible.length" class="empty">Không có lần nhập PIN nào.</div>
        <ul v-else class="events">
          <li v-for="event in visible" :key="event.id" :class="{ bad: !event.ok }">
            <span class="badge">{{ event.ok ? "✓" : "!" }}</span>
            <div style="flex: 1 1 200px; min-width: 0">
              <div style="font-weight: 800">{{ title(event) }}</div>
              <div class="muted" style="font-size: 14px">{{ detail(event) }}</div>
            </div>
            <span style="font-weight: 800; min-width: 96px; text-align: right">{{
              event.ok ? money(event.amount) : "—"
            }}</span>
            <span class="mono muted" style="font-size: 13px; min-width: 70px; text-align: right">{{
              time(event.created_at)
            }}</span>
          </li>
        </ul>
      </div>

      <aside class="narrow" style="display: flex; flex-direction: column; gap: 16px">
        <div class="dark-card">
          <span class="round-icon" style="background: var(--cobalt)"
            ><AIcon name="lock" :size="24" :stroke="2.2"
          /></span>
          <div style="font-family: var(--display); font-weight: 800; font-size: 20px">PIN nhân viên</div>
          <p>Nhập sai 5 lần liên tiếp, bàn phím khoá 30 giây. Đổi PIN khi có nhân viên nghỉ việc.</p>
          <router-link
            to="/settings"
            class="btn"
            style="background: var(--white); color: var(--ink); font-weight: 800"
            >Đổi PIN</router-link
          >
        </div>
        <div
          v-if="latestFailure"
          class="alert error"
          style="flex-direction: column; align-items: flex-start; border-radius: 26px; padding: 20px"
        >
          <strong style="color: var(--red-fg)"
            >{{ badEvents.length }} lần nhập sai · gần nhất lúc {{ time(latestFailure.created_at) }}</strong
          >
          <span style="font-size: 14px; color: #6b1a26; line-height: 1.5"
            >Phiên {{ sessionCode(latestFailure.session_id) }}. Nếu lặp lại nhiều, hãy kiểm tra ai đang thử
            PIN trên máy.</span
          >
        </div>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.events {
  display: flex;
  flex-direction: column;
  gap: 8px;
  list-style: none;
  margin: 0;
  padding: 0;
}
.events li {
  align-items: center;
  background: var(--panel);
  border-radius: 18px;
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  padding: 12px 14px;
}
.events li.bad {
  background: var(--red-bg);
  border: 1.5px solid #f4a3ae;
}
.badge {
  align-items: center;
  background: var(--green-bg);
  border-radius: 50%;
  color: var(--green-fg);
  display: flex;
  flex: none;
  font-weight: 800;
  height: 40px;
  justify-content: center;
  width: 40px;
}
.bad .badge {
  background: var(--red);
  color: var(--white);
}
</style>
