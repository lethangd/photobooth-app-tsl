<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { login } from "../api";
import AIcon from "../components/AIcon.vue";
import { errorText } from "../state";

const route = useRoute();
const router = useRouter();
const password = ref("");
const show = ref(false);
const busy = ref(false);
const error = ref("");

async function submit(): Promise<void> {
  if (!password.value || busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await login(password.value);
    const next =
      typeof route.query.next === "string" && route.query.next.startsWith("/") ? route.query.next : "/";
    await router.replace(next);
  } catch (exc) {
    error.value = errorText(exc);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="login">
    <span class="deco deco-a" aria-hidden="true" />
    <span class="deco deco-b" aria-hidden="true" />
    <span class="deco deco-c" aria-hidden="true" />
    <div class="login-ring">
      <form class="login-card" @submit.prevent="submit">
        <div class="brand" style="padding: 0">
          <span class="brand-ball" style="width: 36px; height: 36px" />
          <span class="brand-name" style="font-size: 24px">TSL</span>
          <span class="brand-tag">admin</span>
        </div>
        <div>
          <h1 class="h1" style="font-size: 30px; margin: 0">Đăng nhập</h1>
          <p class="muted" style="margin: 8px 0 0; font-size: 15px">
            Quản lý doanh thu, khung ảnh và thiết bị của kiosk.
          </p>
        </div>
        <label class="field" style="font-size: 16px">
          Mật khẩu
          <span
            class="input-wrap"
            :style="{
              borderColor: error ? 'var(--red)' : 'var(--cobalt)',
              borderWidth: '2px',
              background: '#fff',
              height: '56px',
            }"
          >
            <input
              v-model="password"
              :type="show ? 'text' : 'password'"
              autocomplete="current-password"
              autofocus
              style="font-size: 18px; letter-spacing: 0.1em"
              @input="error = ''"
            />
            <button
              type="button"
              class="icon-btn"
              style="width: 42px; height: 42px; border: 0; background: var(--soft)"
              :aria-label="show ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'"
              @click="show = !show"
            >
              <AIcon name="eye" />
            </button>
          </span>
        </label>
        <p v-if="error" role="alert" style="margin: -8px 0 0; color: #b4142a; font-weight: 700">
          {{ error }}
        </p>
        <button type="submit" class="btn btn-primary login-btn" :disabled="busy || !password">
          {{ busy ? "Đang kiểm tra…" : "Vào trang quản trị" }}
          <span class="login-arrow"><AIcon name="arrow-right" :stroke="2.6" /></span>
        </button>
        <p class="muted" style="margin: 0; font-size: 13px; line-height: 1.5">
          Quên mật khẩu? Mở file <span class="mono">config/config.json</span> trên máy kiosk, hoặc liên hệ
          người cài đặt.
        </p>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login {
  align-items: center;
  display: flex;
  justify-content: center;
  min-height: 100vh;
  overflow: hidden;
  padding: 40px 16px;
  position: relative;
}
.deco {
  position: absolute;
}
.deco-a {
  background: var(--lilac);
  border-radius: 120px;
  height: 240px;
  right: -120px;
  top: 80px;
  transform: rotate(-20deg);
  width: 640px;
}
.deco-b {
  background: var(--mint);
  border-radius: 75px;
  bottom: 60px;
  height: 150px;
  left: -80px;
  transform: rotate(16deg);
  width: 380px;
}
.deco-c {
  background: var(--chrome-ball);
  border-radius: 50%;
  box-shadow: 0 24px 48px rgba(20, 22, 28, 0.2);
  height: 120px;
  left: 18%;
  top: 12%;
  width: 120px;
}
.login-ring {
  background: var(--chrome);
  border-radius: 40px;
  box-shadow: 0 30px 70px rgba(20, 22, 28, 0.25);
  max-width: 460px;
  padding: 10px;
  position: relative;
  width: 100%;
}
.login-card {
  background: var(--white);
  border-radius: 30px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 36px 32px;
}
.login-btn {
  font-family: var(--display);
  font-size: 17px;
  font-weight: 600;
  height: 60px;
  justify-content: space-between;
  padding: 0 8px 0 26px;
}
.login-arrow {
  align-items: center;
  background: var(--white);
  border-radius: 50%;
  color: var(--cobalt);
  display: flex;
  height: 46px;
  justify-content: center;
  width: 46px;
}
</style>
