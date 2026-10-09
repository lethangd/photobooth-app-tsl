import { createApp } from "vue";
import { createRouter, createWebHashHistory } from "vue-router";

import { token } from "./api";
import AdminApp from "./AdminApp.vue";
import "./admin.css";
import DashboardPage from "./pages/DashboardPage.vue";
import DevicesPage from "./pages/DevicesPage.vue";
import FramesPage from "./pages/FramesPage.vue";
import LoginPage from "./pages/LoginPage.vue";
import MulticamPage from "./pages/MulticamPage.vue";
import PinPage from "./pages/PinPage.vue";
import SessionsPage from "./pages/SessionsPage.vue";
import SettingsPage from "./pages/SettingsPage.vue";

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", component: DashboardPage, meta: { title: "Tổng quan" } },
    { path: "/sessions", component: SessionsPage, meta: { title: "Phiên & doanh thu" } },
    { path: "/pin", component: PinPage, meta: { title: "Nhật ký PIN" } },
    { path: "/frames", component: FramesPage, meta: { title: "Khung ảnh" } },
    { path: "/devices", component: DevicesPage, meta: { title: "Máy in & camera" } },
    { path: "/multicam", component: MulticamPage, meta: { title: "Multicamera" } },
    { path: "/settings", component: SettingsPage, meta: { title: "Cài đặt kiosk" } },
    { path: "/login", component: LoginPage, meta: { title: "Đăng nhập", public: true } },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
  scrollBehavior: () => ({ top: 0 }),
});

router.beforeEach((to) => {
  if (!to.meta.public && !token.value) return { path: "/login", query: { next: to.fullPath } };
  if (to.path === "/login" && token.value) return "/";
  return true;
});

router.afterEach((to) => {
  document.title = `${String(to.meta.title ?? "Quản trị")} · TSL Photobooth`;
});

createApp(AdminApp).use(router).mount("#admin");
