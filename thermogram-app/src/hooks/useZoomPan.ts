import { RefObject, useEffect, useLayoutEffect, useRef } from "react";

interface UseZoomPanOptions {
  containerRef: RefObject<HTMLElement | null>;
  contentRef: RefObject<HTMLElement | null>;
  zoom: number;
  setZoom: (z: number) => void;
  minZoom: number;
  maxZoom: number;
  // Tunable: larger = faster zoom per wheel delta
  zoomSpeed?: number;
}

export function useZoomPan({
  containerRef,
  contentRef,
  zoom,
    setZoom,
  minZoom,
  maxZoom,
  zoomSpeed = 0.01,
}: UseZoomPanOptions) {
  const pendingFocusRef = useRef<{
    imageX: number;
    imageY: number;
    mouseX: number;
    mouseY: number;
  } | null>(null);

  const zoomRef = useRef(zoom);
  useEffect(() => {
    zoomRef.current = zoom;
  }, [zoom]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const handler = (e: WheelEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      e.preventDefault();
      const content = contentRef.current;
      if (!content) return;

      const contentRect = content.getBoundingClientRect();
      const currentZoom = zoomRef.current;
      // Image-space coordinate under cursor (independent of zoom).
      const imageX = (e.clientX - contentRect.left) / currentZoom;
      const imageY = (e.clientY - contentRect.top) / currentZoom;

      let dy = e.deltaY;
      if (e.deltaMode === 1) dy *= 16;
      else if (e.deltaMode === 2) dy *= 100;

      const factor = Math.exp(-dy * zoomSpeed);
      const newZoom = Math.max(minZoom, Math.min(maxZoom, currentZoom * factor));
      if (newZoom === currentZoom) return;

      pendingFocusRef.current = {
        imageX,
        imageY,
        mouseX: e.clientX,
        mouseY: e.clientY,
      };
      setZoom(newZoom);
    };

    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, [containerRef, contentRef, setZoom, minZoom, maxZoom, zoomSpeed]);

  useLayoutEffect(() => {
    const focus = pendingFocusRef.current;
    if (!focus) return;
    const el = containerRef.current;
    const content = contentRef.current;
    if (!el || !content) return;

    const contentRect = content.getBoundingClientRect();
    const desiredContentX = focus.imageX * zoom;
    const desiredContentY = focus.imageY * zoom;
    el.scrollLeft += contentRect.left + desiredContentX - focus.mouseX;
    el.scrollTop += contentRect.top + desiredContentY - focus.mouseY;
    pendingFocusRef.current = null;
  }, [zoom, containerRef, contentRef]);
}
