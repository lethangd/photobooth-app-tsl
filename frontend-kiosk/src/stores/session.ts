import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { getConfig } from "@/api/framebooth";
import type {
  CaptureResult,
  FilterOption,
  FrameTemplateSummary,
  FrameTypeConfig,
  KioskConfig,
  RenderResult,
} from "@/api/types";

function newSessionId(): string {
  return `PB${Date.now().toString().slice(-6)}`;
}

export const useSessionStore = defineStore("session", () => {
  const config = ref<KioskConfig | null>(null);
  const sessionId = ref<string>(newSessionId());

  const selectedSlotCount = ref<number | null>(null);
  const digitalDeliveryEnabled = ref<boolean>(true);
  const captures = ref<CaptureResult[]>([]);
  const selectedCaptureIds = ref<string[]>([]);
  const filterId = ref<string>("natural");
  const selectedTemplateId = ref<string>("");
  const finalResult = ref<RenderResult | null>(null);

  const packageConfig = computed<FrameTypeConfig | null>(
    () => config.value?.frame_types.find((f) => f.slot_count === selectedSlotCount.value) ?? null,
  );
  const slotCount = computed<number>(() => selectedSlotCount.value ?? 0);
  const shotsToTake = computed<number>(() => packageConfig.value?.shots_to_take ?? 0);
  const templatesForPackage = computed<FrameTemplateSummary[]>(() => packageConfig.value?.templates ?? []);
  const selectedTemplate = computed<FrameTemplateSummary | null>(() => {
    const list = templatesForPackage.value;
    return list.find((t) => t.id === selectedTemplateId.value) ?? list[0] ?? null;
  });
  const selectedFilter = computed<FilterOption | null>(() => {
    const list = config.value?.filters ?? [];
    return list.find((f) => f.id === filterId.value) ?? list[0] ?? null;
  });
  const selectedCaptures = computed<CaptureResult[]>(() =>
    selectedCaptureIds.value
      .map((id) => captures.value.find((c) => c.id === id))
      .filter((c): c is CaptureResult => Boolean(c)),
  );
  const hasExactSelection = computed<boolean>(
    () => selectedCaptureIds.value.length === slotCount.value && slotCount.value > 0,
  );

  async function loadConfig(): Promise<KioskConfig> {
    const loaded = await getConfig();
    config.value = loaded;
    digitalDeliveryEnabled.value = loaded.digital_delivery_default_enabled ?? true;
    return loaded;
  }

  function resetSession(): void {
    sessionId.value = newSessionId();
    selectedSlotCount.value = null;
    digitalDeliveryEnabled.value = config.value?.digital_delivery_default_enabled ?? true;
    captures.value = [];
    selectedCaptureIds.value = [];
    filterId.value = "natural";
    selectedTemplateId.value = "";
    finalResult.value = null;
  }

  function selectPackage(nextSlotCount: number): void {
    selectedSlotCount.value = nextSlotCount;
    captures.value = [];
    selectedCaptureIds.value = [];
    filterId.value = "natural";
    selectedTemplateId.value = packageConfig.value?.templates[0]?.id ?? "";
    finalResult.value = null;
  }

  function toggleDigitalDelivery(): void {
    digitalDeliveryEnabled.value = !digitalDeliveryEnabled.value;
  }

  function addCapture(capture: CaptureResult): void {
    captures.value.push(capture);
  }

  function clearCaptures(): void {
    captures.value = [];
    selectedCaptureIds.value = [];
  }

  function toggleCaptureSelection(id: string): void {
    const index = selectedCaptureIds.value.indexOf(id);
    if (index >= 0) {
      selectedCaptureIds.value.splice(index, 1);
    } else if (selectedCaptureIds.value.length < slotCount.value) {
      selectedCaptureIds.value.push(id);
    }
  }

  function autoSelectFirstN(): void {
    selectedCaptureIds.value = captures.value.slice(0, slotCount.value).map((c) => c.id);
  }

  function selectFilter(id: string): void {
    filterId.value = id;
  }

  function selectTemplate(id: string): void {
    selectedTemplateId.value = id;
  }

  function ensureTemplateSelected(): void {
    if (!selectedTemplateId.value) {
      selectedTemplateId.value = templatesForPackage.value[0]?.id ?? "";
    }
  }

  function setFinalResult(result: RenderResult | null): void {
    finalResult.value = result;
  }

  return {
    config,
    sessionId,
    selectedSlotCount,
    digitalDeliveryEnabled,
    captures,
    selectedCaptureIds,
    filterId,
    selectedTemplateId,
    finalResult,
    packageConfig,
    slotCount,
    shotsToTake,
    templatesForPackage,
    selectedTemplate,
    selectedFilter,
    selectedCaptures,
    hasExactSelection,
    loadConfig,
    resetSession,
    selectPackage,
    toggleDigitalDelivery,
    addCapture,
    clearCaptures,
    toggleCaptureSelection,
    autoSelectFirstN,
    selectFilter,
    selectTemplate,
    ensureTemplateSelected,
    setFinalResult,
  };
});
