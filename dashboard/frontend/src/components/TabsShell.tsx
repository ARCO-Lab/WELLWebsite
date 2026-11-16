// The dashboard's tabs, holding which one is shown. The page passes its panels in as children: when the shown tab
// changes, only this component re-renders (React keeps the children it was given), so the tab bar and the panel
// switch at once, and the page's own state follows in a transition (onShow). Before, the shown tab was the page's
// state, and every switch re-rendered the whole dashboard first: 0.6-0.8 s at 4x CPU slowdown.

import React, { createContext, useCallback, useContext, useImperativeHandle, useState } from "react";
import { Tabs } from "@/components/animations/tabs";

export type TabName = "sensor" | "sampling";

const ShownTab = createContext<TabName>("sensor");

/** Renders its children only while `tab` is shown (Download, which stops its polling when unmounted). */
export function ShownOnly({ tab, children }: { tab: TabName; children: React.ReactNode }) {
  return useContext(ShownTab) === tab ? <>{children}</> : null;
}

export interface TabsShellHandle { show(tab: TabName): void }

interface Props {
  className?: string;
  onShow: (tab: TabName) => void;
  children: React.ReactNode;
  ref?: React.Ref<TabsShellHandle>;
}

export default function TabsShell({ className, onShow, children, ref }: Props) {
  const [shown, setShown] = useState<TabName>("sensor");
  const show = useCallback((tab: TabName) => {
    setShown(tab);
    onShow(tab);
  }, [onShow]);
  useImperativeHandle(ref, () => ({ show }), [show]);
  return (
    <ShownTab.Provider value={shown}>
      <Tabs value={shown} onValueChange={(v) => show(v as TabName)} className={className}>
        {children}
      </Tabs>
    </ShownTab.Provider>
  );
}
