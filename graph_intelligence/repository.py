"""Persistence queries for normalized graph intelligence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database.models.graphs import Graph, GraphEvent, GraphPoint, GraphStatistics


class GraphRepository:
    """Store immutable graph snapshots and retrieve their complete history."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_graph(self, **data: Any) -> Graph:
        graph = Graph(**data)
        self.session.add(graph)
        self.session.flush()
        return graph

    def add_points(self, graph: Graph, points: list[dict[str, Any]]) -> list[GraphPoint]:
        rows = [GraphPoint(graph_id=graph.id, **point) for point in points]
        self.session.add_all(rows)
        self.session.flush()
        return rows

    def add_statistics(self, graph: Graph, **data: Any) -> GraphStatistics:
        row = GraphStatistics(graph_id=graph.id, **data)
        self.session.add(row)
        self.session.flush()
        return row

    def add_events(self, graph: Graph, events: list[dict[str, Any]]) -> list[GraphEvent]:
        rows = [GraphEvent(graph_id=graph.id, **event) for event in events]
        self.session.add_all(rows)
        self.session.flush()
        return rows

    def get_graph(self, graph_id: Any) -> Graph | None:
        statement = (
            select(Graph)
            .where(Graph.id == graph_id)
            .options(selectinload(Graph.points), selectinload(Graph.statistics), selectinload(Graph.events))
        )
        return self.session.scalars(statement).first()

    def get_graph_points(self, graph_id: Any, start: datetime | None = None, end: datetime | None = None) -> list[GraphPoint]:
        statement = select(GraphPoint).where(GraphPoint.graph_id == graph_id)
        if start is not None:
            statement = statement.where(GraphPoint.timestamp >= start)
        if end is not None:
            statement = statement.where(GraphPoint.timestamp <= end)
        return list(self.session.scalars(statement.order_by(GraphPoint.timestamp)))

    def get_statistics(self, graph_id: Any) -> GraphStatistics | None:
        return self.session.scalars(select(GraphStatistics).where(GraphStatistics.graph_id == graph_id)).first()

    def get_events(self, graph_id: Any) -> list[GraphEvent]:
        statement = select(GraphEvent).where(GraphEvent.graph_id == graph_id).order_by(GraphEvent.timestamp)
        return list(self.session.scalars(statement))

    def get_history(
        self,
        graph_type: str,
        *,
        channel_id: Any | None = None,
        video_id: Any | None = None,
        limit: int = 100,
    ) -> list[Graph]:
        statement = select(Graph).where(Graph.graph_type == graph_type)
        if channel_id is not None:
            statement = statement.where(Graph.channel_id == channel_id)
        if video_id is not None:
            statement = statement.where(Graph.video_id == video_id)
        statement = statement.order_by(Graph.collected_at.desc()).limit(limit)
        return list(self.session.scalars(statement))

    def latest(self, graph_type: str, *, channel_id: Any | None = None, video_id: Any | None = None) -> Graph | None:
        history = self.get_history(graph_type, channel_id=channel_id, video_id=video_id, limit=1)
        return history[0] if history else None
