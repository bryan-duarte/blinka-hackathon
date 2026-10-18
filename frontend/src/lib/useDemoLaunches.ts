import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { DemoLaunchView } from "./types";

const LAUNCH_POLL_MS = 2000;
const LOST_LAUNCH_ERROR = "Progress was lost (the server restarted or the demo was reset).";

type LaunchesByScenario = Record<string, DemoLaunchView>;

export function useDemoLaunches(onStepInjected: () => void) {
  const [launches, setLaunches] = useState<LaunchesByScenario>({});
  const launchesRef = useRef<LaunchesByScenario>({});
  const runningLaunchIds = Object.values(launches)
    .filter((launch) => launch.status === "running")
    .map((launch) => launch.launch_id)
    .join(",");

  const store = useCallback((updatedLaunches: DemoLaunchView[]) => {
    const nextLaunches = {
      ...launchesRef.current,
      ...Object.fromEntries(updatedLaunches.map((launch) => [launch.scenario_id, launch])),
    };
    launchesRef.current = nextLaunches;
    setLaunches(nextLaunches);
  }, []);

  const track = useCallback((launch: DemoLaunchView) => store([launch]), [store]);

  const clear = useCallback(() => {
    launchesRef.current = {};
    setLaunches({});
  }, []);

  useEffect(() => {
    if (!runningLaunchIds) return;
    let isCancelled = false;
    const pollTimer = setInterval(() => {
      const launchIds = runningLaunchIds.split(",");
      Promise.allSettled(launchIds.map((launchId) => api.demoLaunch(launchId))).then((outcomes) => {
        if (isCancelled) return;
        const refreshed = outcomes.map((outcome, index) =>
          outcome.status === "fulfilled" ? outcome.value : lostLaunch(launchesRef.current, launchIds[index]),
        );
        const knownLaunches = refreshed.filter((launch): launch is DemoLaunchView => launch !== null);
        const hasNewStep = knownLaunches.some((launch) =>
          hasInjectedNewStep(launchesRef.current[launch.scenario_id], launch),
        );
        store(knownLaunches);
        if (hasNewStep) onStepInjected();
      });
    }, LAUNCH_POLL_MS);
    return () => {
      isCancelled = true;
      clearInterval(pollTimer);
    };
  }, [runningLaunchIds, onStepInjected, store]);

  return { launches, track, clear };
}

function lostLaunch(launches: LaunchesByScenario, launchId: string): DemoLaunchView | null {
  const launch = Object.values(launches).find((tracked) => tracked.launch_id === launchId);
  if (!launch) return null;
  return { ...launch, status: "failed", error: LOST_LAUNCH_ERROR };
}

function hasInjectedNewStep(previous: DemoLaunchView | undefined, next: DemoLaunchView): boolean {
  const previousEmailIds = new Set(previous?.steps.map((step) => step.email_id) ?? []);
  return next.steps.some((step) => step.email_id !== null && !previousEmailIds.has(step.email_id));
}
