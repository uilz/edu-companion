"use client";

import React, { useRef, useEffect, useState, useCallback } from "react";
import * as d3 from "d3";
import type { GraphData, LayoutNode, GraphNode } from "@/lib/types/graph-types";
import { getMasteryColor, getNodeRadius } from "@/lib/types/graph-types";

interface ForceGraphProps {
  data: GraphData;
  selectedNodeId?: string;
  onNodeSelect?: (node: GraphNode) => void;
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
  const [nodes, setNodes] = useState<LayoutNode[]>([]);
  const simulationRef = useRef<d3.Simulation<LayoutNode, undefined> | null>(null);

  // Initialize layout
  useEffect(() => {
    if (!data.nodes.length) return;

    const layoutNodes: LayoutNode[] = data.nodes.map((n) => ({
      ...n,
      x: width / 2 + (Math.random() - 0.5) * width * 0.5,
      y: height / 2 + (Math.random() - 0.5) * height * 0.5,
    }));

    setNodes(layoutNodes);
  }, [data, width, height]);

  // D3 simulation
  useEffect(() => {
    if (!nodes.length || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    // Define arrow markers
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
      .data(nodes)
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

    // Node circles
    nodeGroup
      .append("circle")
      .attr("r", (d) => getNodeRadius(d.level))
      .attr("fill", (d) => getMasteryColor(d.mastery))
      .attr("stroke", (d) =>
        d.id === selectedNodeId ? "var(--color-accent)" : "var(--color-surface)"
      )
      .attr("stroke-width", (d) => (d.id === selectedNodeId ? 3 : 1.5))
      .attr("opacity", 0.9);

    // Node labels
    nodeGroup
      .append("text")
      .text((d) => d.label.length > 8 ? d.label.slice(0, 8) + "…" : d.label)
      .attr("dx", (d) => getNodeRadius(d.level) + 4)
      .attr("dy", 4)
      .attr("font-size", (d) => (d.level === "partition" ? 11 : 9))
      .attr("fill", "var(--color-text)")
      .attr("opacity", 0.8);

    // Click handler
    nodeGroup.on("click", (event, d) => {
      event.stopPropagation();
      onNodeSelect?.(d);
    });

    // Right-click handler
    nodeGroup.on("contextmenu", (event, d) => {
      event.preventDefault();
      event.stopPropagation();
      onNodeContextMenu?.(d, event);
    });

    // Simulation
    const simulation = d3
      .forceSimulation<LayoutNode>(nodes)
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

    simulationRef.current = simulation;

    return () => {
      simulation.stop();
    };
  }, [nodes, data.edges, selectedNodeId, onNodeSelect, width, height]);

  return (
    <div ref={containerRef} className="w-full h-full">
      <svg
        ref={svgRef}
        className="w-full h-full"
      />
    </div>
  );
}
