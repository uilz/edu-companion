"use client";

import { useRef, useEffect } from "react";
import type { GraphData, LayoutNode, GraphNode } from "@/lib/types/graph-types";
import { getMasteryColor, getNodeRadius } from "@/lib/types/graph-types";

let d3Module: any = null;

async function getD3() {
  if (!d3Module) {
    d3Module = await import("d3");
  }
  return d3Module;
}

interface ForceGraphProps {
  data: GraphData;
  selectedNodeId?: string;
  onNodeSelect?: (node: GraphNode, pos?: { x: number; y: number }) => void;
  onNodeContextMenu?: (node: GraphNode, e: MouseEvent) => void;
  width: number;
  height: number;
}

export default function ForceGraph({
  data,
  selectedNodeId,
  onNodeSelect,
  onNodeContextMenu,
  width,
  height,
}: ForceGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const onNodeSelectRef = useRef(onNodeSelect);
  onNodeSelectRef.current = onNodeSelect;
  const onNodeContextMenuRef = useRef(onNodeContextMenu);
  onNodeContextMenuRef.current = onNodeContextMenu;
  const selectedNodeIdRef = useRef(selectedNodeId);
  selectedNodeIdRef.current = selectedNodeId;

  useEffect(() => {
    if (!data.nodes.length || !svgRef.current) return;

    let cancelled = false;
    const svgEl = svgRef.current;

    getD3().then((d3) => {
      if (cancelled) return;

      const svg = d3.select(svgEl);
      svg.selectAll("*").remove();

      const layoutNodes: LayoutNode[] = data.nodes.map((n) => ({
        ...n,
        x: width / 2 + (Math.random() - 0.5) * width * 0.5,
        y: height / 2 + (Math.random() - 0.5) * height * 0.5,
      }));

      svg
        .append("defs")
        .append("marker")
        .attr("id", "arrow")
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 20)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .attr("fill", "var(--color-border)");

      const linkElements = svg
        .append("g")
        .selectAll("line")
        .data(data.edges)
        .join("line")
        .attr("stroke", "var(--color-border)")
        .attr("stroke-width", 1.5)
        .attr("stroke-opacity", 0.6)
        .attr("marker-end", "url(#arrow)");

      const nodeGroup = svg
        .append("g")
        .selectAll("g")
        .data(layoutNodes)
        .join("g")
        .style("cursor", "pointer")
        .call(
          d3.drag<SVGGElement, LayoutNode>()
            .on("start", (event, d) => {
              if (!event.active) simulation.alphaTarget(0.3).restart();
              d.fx = d.x;
              d.fy = d.y;
            })
            .on("drag", (event, d) => {
              d.fx = event.x;
              d.fy = event.y;
            })
            .on("end", (event, d) => {
              if (!event.active) simulation.alphaTarget(0);
              d.fx = null;
              d.fy = null;
            }) as any
        );

      nodeGroup
        .append("circle")
        .attr("r", (d) => getNodeRadius(d.level))
        .attr("fill", (d) => getMasteryColor(d.mastery))
        .attr("stroke", (d) =>
          d.id === selectedNodeIdRef.current
            ? "var(--color-accent)"
            : "var(--color-surface)"
        )
        .attr("stroke-width", (d) =>
          d.id === selectedNodeIdRef.current ? 3 : 1.5
        )
        .attr("opacity", 0.9);

      nodeGroup
        .append("text")
        .text((d) =>
          d.label.length > 8 ? d.label.slice(0, 8) + "\u2026" : d.label
        )
        .attr("dx", (d) => getNodeRadius(d.level) + 4)
        .attr("dy", 4)
        .attr("font-size", (d) => (d.level === "partition" ? 11 : 9))
        .attr("fill", "var(--color-text)")
        .attr("opacity", 0.8);

      nodeGroup.on("click", (event, d) => {
        event.stopPropagation();
        onNodeSelectRef.current?.(d, { x: d.x, y: d.y });
      });

      nodeGroup.on("contextmenu", (event, d) => {
        event.preventDefault();
        event.stopPropagation();
        onNodeContextMenuRef.current?.(d, event);
      });

      const simulation = d3
        .forceSimulation<LayoutNode>(layoutNodes)
        .force(
          "link",
          d3
            .forceLink<LayoutNode, any>(data.edges)
            .id((d) => d.id)
            .distance(100)
            .strength(0.3)
        )
        .force("charge", d3.forceManyBody().strength(-200))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide().radius(25))
        .on("tick", () => {
          linkElements
            .attr("x1", (d: any) => d.source.x)
            .attr("y1", (d: any) => d.source.y)
            .attr("x2", (d: any) => d.target.x)
            .attr("y2", (d: any) => d.target.y);

          nodeGroup.attr("transform", (d) => `translate(${d.x},${d.y})`);
        });

      return () => {
        simulation.stop();
      };
    });

    return () => {
      cancelled = true;
    };
  }, [data, width, height]);

  return (
    <div ref={containerRef} className="w-full h-full">
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}
