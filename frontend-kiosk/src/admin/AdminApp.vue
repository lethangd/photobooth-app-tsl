<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { setToken, token } from "./api";
import AIcon from "./components/AIcon.vue";
import { startSummaryPolling, summary, toast } from "./state";

const route = useRoute();
const router = useRouter();
const moreOpen = ref(false);

const navItems = computed(() => [
  { to: "/", icon: "home", label: "Tổng quan", badge: "" },
  { to: "/sessions", icon: "receipt", label: "Phiên & doanh thu", badge: "" },
  {
    to: "/pin",
    icon: "lock",
    label: "Nhật ký PIN",
    badge: summary.pinFailed ? `${summary.pinFailed} sai` : "",
  },
  { to: "/frames", icon: "frame", label: "Khung ảnh", badge: "" },
  { to: "/devices", icon: "printer", label: "Máy in & camera", badge: summary.printerIssue ? "1" : "" },
  { to: "/multicam", icon: "cube", label: "Multicamera", badge: "" },
  { to: "/settings", icon: "gear", label: "Cài đặt kiosk", badge: "" },
]);
const TAB_LABELS: Record<string, string> = {
  "/": "Tổng quan",
  "/sessions": "Phiên",
  "/devices": "Máy in",
  "/settings": "Cài đặt",
};
const tabs = computed(() =>
  navItems.value
    .filter((item) => item.to in TAB_LABELS)
    .map((item) => ({ ...item, short: TAB_LABELS[item.to] })),
);
const isPublic = computed(() => Boolean(route.meta.public));

function isActive(path: string): boolean {
  return path === "/" ? route.path === "/" : route.path.startsWith(path);
}

function logout(): void {
  setToken("");
  void router.push("/login");
}

watch(token, (value) => {
  if (!value && !isPublic.value) void router.push({ path: "/login", query: { next: route.fullPath } });
  if (value) startSummaryPolling();
});

watch(
  () => route.fullPath,
  () => (moreOpen.value = false),
);

onMounted(() => {
  if (token.value) startSummaryPolling();
});
</script>

<template>
  <router-view v-if="isPublic" />

  <div v-else class="adm">
    <nav class="side" aria-label="Menu quản trị">
      <router-link to="/" class="brand">
        <span class="brand-ball" />
        <span class="brand-name">TSL</span>
        <span class="brand-tag">admin</span>
      </router-link>
      <div class="nav">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ active: isActive(item.to) }"
        >
          <AIcon :name="item.icon" />
          <span>{{ item.label }}</span>
          <em v-if="item.badge" class="nav-badge">{{ item.badge }}</em>
        </router-link>
      </div>
      <div class="side-foot">
        <div class="kiosk-card">
          <div class="state">
            <span class="dot" :class="summary.online ? 'ok' : 'err'" />
            {{ summary.online ? "Kiosk đang chạy" : "Mất kết nối máy chủ" }}
          </div>
          <a href="/" target="_blank" rel="noopener">Mở màn hình kiosk ↗</a>
        </div>
        <button type="button" class="logout" @click="logout">
          <AIcon name="logout" />
          Đăng xuất
        </button>
      </div>
    </nav>

    <header class="mobile-top">
      <router-link to="/" class="brand">
        <span class="brand-ball" style="width: 28px; height: 28px" />
        <span class="brand-name" style="font-size: 19px">TSL</span>
      </router-link>
      <span class="state">
        <span class="dot" :class="summary.online ? 'ok' : 'err'" style="width: 8px; height: 8px" />
        {{ summary.online ? "Kiosk đang chạy" : "Mất kết nối" }}
      </span>
    </header>

    <main class="main">
      <router-view v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" :key="route.path" />
        </Transition>
      </router-view>
    </main>

    <nav class="tabs" aria-label="Menu">
      <router-link
        v-for="item in tabs"
        :key="item.to"
        :to="item.to"
        class="tab"
        :class="{ active: isActive(item.to) }"
      >
        <AIcon :name="item.icon" :size="22" />
        <span>{{ item.short }}</span>
      </router-link>
      <button
        type="button"
        class="tab"
        style="background: none; border: 0"
        :aria-expanded="moreOpen"
        @click="moreOpen = !moreOpen"
      >
        <AIcon name="more" :size="22" :stroke="3" />
        <span>Thêm</span>
      </button>
    </nav>
    <div
      v-if="moreOpen"
      class="modal-back"
      style="align-items: flex-end; padding: 0; z-index: 24"
      @click.self="moreOpen = false"
    >
      <div class="more-sheet">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-item"
          :class="{ active: isActive(item.to) }"
        >
          <AIcon :name="item.icon" />
          <span>{{ item.label }}</span>
          <em v-if="item.badge" class="nav-badge">{{ item.badge }}</em>
        </router-link>
        <button type="button" class="logout" @click="logout"><AIcon name="logout" />Đăng xuất</button>
      </div>
    </div>
  </div>

  <Transition name="toast">
    <div v-if="toast.text" :key="toast.nonce" class="toast" :class="{ error: toast.error }" role="status">
      {{ toast.text }}
    </div>
  </Transition>
</template>
