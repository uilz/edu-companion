"use client";

import dynamic from "next/dynamic";

const FocusPage = dynamic(
  () => import("@/components/focus/FocusPage"),
  { ssr: false }
);

export default function FocusRoute() {
  return <FocusPage />;
}
