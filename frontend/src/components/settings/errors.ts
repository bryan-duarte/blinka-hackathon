import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { ApiError, HTTP_CONFLICT, UnauthorizedError } from "@/lib/api";

const SESSION_EXPIRED = "session_expired";

export type ReportError = (
  error: unknown,
  conflictMessage: string,
  fallbackMessage: string,
) => string | null;

function errorMessage(
  error: unknown,
  conflictMessage: string,
  fallbackMessage: string,
): string {
  if (error instanceof UnauthorizedError) return SESSION_EXPIRED;
  if (error instanceof ApiError && error.status === HTTP_CONFLICT) return conflictMessage;
  return fallbackMessage;
}

export function useReportError(): ReportError {
  const router = useRouter();
  return useCallback(
    (error: unknown, conflictMessage: string, fallbackMessage: string): string | null => {
      const message = errorMessage(error, conflictMessage, fallbackMessage);
      if (message === SESSION_EXPIRED) {
        router.replace("/login");
        return null;
      }
      return message;
    },
    [router],
  );
}
