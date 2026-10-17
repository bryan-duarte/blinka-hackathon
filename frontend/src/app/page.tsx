"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { tokenStore } from "@/lib/api";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace(tokenStore.get() ? "/inbox" : "/login");
  }, [router]);

  return null;
}
