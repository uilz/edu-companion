import { Metadata } from "next";
import ToolsPage from "@/components/tools/ToolsPage";

export const metadata: Metadata = {
  title: "工具箱 — 苹果果",
  description: "闪卡、阅读、语音、画布、手写、番茄钟等学习工具",
};

export default function ToolsRoute() {
  return <ToolsPage />;
}
