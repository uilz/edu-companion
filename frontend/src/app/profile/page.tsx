import { Metadata } from "next";
import ProfilePage from "@/components/profile/ProfilePage";

export const metadata: Metadata = {
  title: "成长画像 — 苹果果",
  description: "查看你的学习画像、目标和成长统计",
};

export default function ProfileRoute() {
  return <ProfilePage />;
}
