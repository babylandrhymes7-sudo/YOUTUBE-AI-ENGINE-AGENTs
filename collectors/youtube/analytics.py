"""YouTube analytics collector.

TODO: Keep analytics ingestion limited to fetching and persisting raw metrics rows.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from app.config import settings
from app.logging import get_logger
from database.repositories.catalog import (
	AnalyticsSnapshotRepository,
	AudienceSnapshotRepository,
	CTRGraphRepository,
	CountryMetricRepository,
	CountryRepository,
	DeviceMetricRepository,
	DeviceRepository,
	RevenueRepository,
	RetentionGraphRepository,
	TrafficSourceMetricRepository,
	TrafficSourceRepository,
	ViewGraphRepository,
)

from .client import YouTubeApiClient
from utils.dates import parse_iso_datetime
from graph_intelligence import GraphInput, GraphPointInput, GraphService


logger = get_logger(__name__)


class AnalyticsCollector:
	"""Fetch and persist YouTube Analytics reports without any downstream analysis."""

	def __init__(
		self,
		client: YouTubeApiClient,
		snapshot_repository: AnalyticsSnapshotRepository,
		retention_repository: RetentionGraphRepository,
		ctr_repository: CTRGraphRepository,
		view_repository: ViewGraphRepository,
		traffic_source_repository: TrafficSourceRepository,
		traffic_source_metric_repository: TrafficSourceMetricRepository,
		audience_repository: AudienceSnapshotRepository,
		country_repository: CountryRepository,
		country_metric_repository: CountryMetricRepository,
		device_repository: DeviceRepository,
		device_metric_repository: DeviceMetricRepository,
		revenue_repository: RevenueRepository,
	) -> None:
		"""Initialize the collector with a client and normalized repositories."""

		self._client = client
		self._snapshot_repository = snapshot_repository
		self._retention_repository = retention_repository
		self._ctr_repository = ctr_repository
		self._view_repository = view_repository
		self._traffic_source_repository = traffic_source_repository
		self._traffic_source_metric_repository = traffic_source_metric_repository
		self._audience_repository = audience_repository
		self._country_repository = country_repository
		self._country_metric_repository = country_metric_repository
		self._device_repository = device_repository
		self._device_metric_repository = device_metric_repository
		self._revenue_repository = revenue_repository
		self._graph_service = GraphService(snapshot_repository.session)

	def collect_channel_analytics(self, channel_database_id: Any, video_database_ids: Iterable[Any], start_date: date, end_date: date) -> None:
		"""Collect and persist channel-level analytics for the requested date range."""

		snapshot = self._upsert_snapshot(channel_database_id, None, start_date, end_date, "channel")
		self._collect_channel_totals(snapshot, start_date, end_date)
		self._collect_channel_graphs(snapshot, start_date, end_date)
		self._collect_traffic_sources(snapshot, start_date, end_date)
		self._collect_audience(snapshot, start_date, end_date)
		self._collect_countries(snapshot, start_date, end_date)
		self._collect_devices(snapshot, start_date, end_date)
		self._collect_revenue(snapshot, start_date, end_date)

		for video_database_id in video_database_ids:
			video_snapshot = self._upsert_snapshot(channel_database_id, video_database_id, start_date, end_date, "video")
			self._collect_video_graphs(video_snapshot, video_database_id, start_date, end_date)
			self._collect_retention(video_snapshot, video_database_id, start_date, end_date)

	def _upsert_snapshot(self, channel_database_id: Any, video_database_id: Any | None, start_date: date, end_date: date, scope: str) -> Any:
		"""Insert or update a normalized analytics snapshot row."""

		data = {
			"channel_id": channel_database_id,
			"video_id": video_database_id,
			"scope": scope,
			"snapshot_date": end_date,
			"collected_at": datetime.now(timezone.utc),
			"views": 0,
			"likes": 0,
			"comments": 0,
			"shares": 0,
			"impressions": 0,
		}
		existing = self._snapshot_repository.get_one_by(
			channel_id=channel_database_id, video_id=video_database_id, snapshot_date=end_date, scope=scope
		)
		if existing is not None:
			return self._snapshot_repository.update(existing, **data)
		return self._snapshot_repository.create(**data)

	def _collect_channel_totals(self, snapshot: Any, start_date: date, end_date: date) -> None:
		"""Fetch aggregate channel metrics and write them to the snapshot row."""

		payload = self._client.query_analytics(
			ids=settings.youtube_analytics_ids,
			startDate=start_date.isoformat(),
			endDate=end_date.isoformat(),
			metrics="views,likes,comments,shares,estimatedMinutesWatched,averageViewDuration,impressions,impressionsClickThroughRate,subscribersGained",
		)
		row = payload.get("rows", [None])[0]
		if not row:
			return
		snapshot.views = int(row[0] or 0)
		snapshot.likes = int(row[1] or 0)
		snapshot.comments = int(row[2] or 0)
		snapshot.shares = int(row[3] or 0)
		snapshot.watch_time_hours = float(row[4] or 0) / 60.0
		snapshot.avg_view_duration_seconds = int(row[5] or 0)
		snapshot.impressions = int(row[6] or 0)
		snapshot.click_through_rate = float(row[7] or 0)
		snapshot.subscribers_gained = int(row[8] or 0)

	def _collect_channel_graphs(self, snapshot: Any, start_date: date, end_date: date) -> None:
		"""Persist daily views and CTR graph rows for the channel snapshot."""

		views_payload = self._client.query_analytics(
			ids=settings.youtube_analytics_ids,
			startDate=start_date.isoformat(),
			endDate=end_date.isoformat(),
			metrics="views",
			dimensions="day",
		)
		ctr_payload = self._client.query_analytics(
			ids=settings.youtube_analytics_ids,
			startDate=start_date.isoformat(),
			endDate=end_date.isoformat(),
			metrics="impressions,impressionsClickThroughRate,views",
			dimensions="day",
		)

		self._view_repository.delete_where(snapshot_id=snapshot.id)
		self._ctr_repository.delete_where(snapshot_id=snapshot.id)

		for index, row in enumerate(views_payload.get("rows", []) or []):
			collected_at = parse_iso_datetime(row[0]) or datetime.now(timezone.utc)
			self._view_repository.create(snapshot_id=snapshot.id, point_index=index, observed_at=collected_at, views=int(row[1] or 0))

		for index, row in enumerate(ctr_payload.get("rows", []) or []):
			self._ctr_repository.create(
				snapshot_id=snapshot.id,
				point_index=index,
				elapsed_seconds=index,
				impressions=int(row[1] or 0),
				clicks=0,
				ctr_percent=float(row[2] or 0),
			)

		self._ingest_time_graph(
			"views", "Channel Views", views_payload.get("rows", []) or [], snapshot, value_index=1, unit="count"
		)
		self._ingest_time_graph(
			"ctr", "Channel CTR", ctr_payload.get("rows", []) or [], snapshot, value_index=2, unit="percent"
		)

	def _collect_traffic_sources(self, snapshot: Any, start_date: date, end_date: date) -> None:
		"""Persist traffic source metrics for a channel snapshot."""

		payload = self._client.query_analytics(
			ids=settings.youtube_analytics_ids,
			startDate=start_date.isoformat(),
			endDate=end_date.isoformat(),
			metrics="views,estimatedMinutesWatched,impressions,impressionsClickThroughRate",
			dimensions="trafficSourceType",
		)
		self._traffic_source_metric_repository.delete_where(snapshot_id=snapshot.id)
		for row in payload.get("rows", []) or []:
			source_type = row[0]
			source = self._traffic_source_repository.get_one_by(source_key=source_type)
			if source is None:
				source = self._traffic_source_repository.create(source_key=source_type, source_type=source_type, name=source_type)
			self._traffic_source_metric_repository.create(
				snapshot_id=snapshot.id,
				traffic_source_id=source.id,
				views=int(row[1] or 0),
				watch_time_hours=float(row[2] or 0) / 60.0,
				impressions=int(row[3] or 0),
				clicks=0,
				ctr_percent=float(row[4] or 0) if len(row) > 4 and row[4] is not None else None,
			)

	def _collect_audience(self, snapshot: Any, start_date: date, end_date: date) -> None:
		"""Persist audience metrics for subscribed and non-subscribed viewers."""

		payload = self._client.query_analytics(
			ids=settings.youtube_analytics_ids,
			startDate=start_date.isoformat(),
			endDate=end_date.isoformat(),
			metrics="views,estimatedMinutesWatched",
			dimensions="subscriberStatus",
		)
		audience = self._audience_repository.get_one_by(snapshot_id=snapshot.id)
		if audience is None:
			audience = self._audience_repository.create(snapshot_id=snapshot.id)
		audience.total_viewers = sum(int(row[1] or 0) for row in payload.get("rows", []) or [])
		for row in payload.get("rows", []) or []:
			status = row[0]
			if status == "SUBSCRIBED":
				audience.subscribers = int(row[1] or 0)
			else:
				audience.non_subscribers = int(row[1] or 0)
		audience.new_viewers = audience.new_viewers or 0
		audience.returning_viewers = audience.returning_viewers or 0

	def _collect_countries(self, snapshot: Any, start_date: date, end_date: date) -> None:
		"""Persist country-level metrics for the snapshot period."""

		payload = self._client.query_analytics(
			ids=settings.youtube_analytics_ids,
			startDate=start_date.isoformat(),
			endDate=end_date.isoformat(),
			metrics="views,estimatedMinutesWatched,impressions,impressionsClickThroughRate",
			dimensions="country",
		)
		self._country_metric_repository.delete_where(snapshot_id=snapshot.id)
		for row in payload.get("rows", []) or []:
			country_code = row[0]
			country = self._country_repository.get_one_by(country_code=country_code)
			if country is None:
				country = self._country_repository.create(country_code=country_code, name=country_code)
			self._country_metric_repository.create(
				snapshot_id=snapshot.id,
				country_id=country.id,
				views=int(row[1] or 0),
				watch_time_hours=float(row[2] or 0) / 60.0,
				impressions=int(row[3] or 0),
				engagement_rate=float(row[4] or 0) if len(row) > 4 and row[4] is not None else None,
			)

	def _collect_devices(self, snapshot: Any, start_date: date, end_date: date) -> None:
		"""Persist device-level metrics for the snapshot period."""

		payload = self._client.query_analytics(
			ids=settings.youtube_analytics_ids,
			startDate=start_date.isoformat(),
			endDate=end_date.isoformat(),
			metrics="views,estimatedMinutesWatched",
			dimensions="deviceType",
		)
		self._device_metric_repository.delete_where(snapshot_id=snapshot.id)
		for row in payload.get("rows", []) or []:
			device_name = row[0]
			device = self._device_repository.get_one_by(name=device_name)
			if device is None:
				device = self._device_repository.create(name=device_name)
			self._device_metric_repository.create(
				snapshot_id=snapshot.id,
				device_id=device.id,
				views=int(row[1] or 0),
				watch_time_hours=float(row[2] or 0) / 60.0,
				share_of_watch_time=None,
			)

	def _collect_revenue(self, snapshot: Any, start_date: date, end_date: date) -> None:
		"""Persist revenue metrics for the snapshot period."""

		payload = self._client.query_analytics(
			ids=settings.youtube_analytics_ids,
			startDate=start_date.isoformat(),
			endDate=end_date.isoformat(),
			metrics="estimatedRevenue,rpm,cpm",
		)
		row = payload.get("rows", [None])[0]
		if not row:
			return
		revenue = self._revenue_repository.get_one_by(snapshot_id=snapshot.id)
		if revenue is None:
			revenue = self._revenue_repository.create(snapshot_id=snapshot.id, currency="USD")
		revenue.estimated_revenue = float(row[0] or 0)
		revenue.rpm = float(row[1] or 0)
		revenue.cpm = float(row[2] or 0)

	def _collect_video_graphs(self, snapshot: Any, video_database_id: Any, start_date: date, end_date: date) -> None:
		"""Persist daily view and CTR graph rows for a video snapshot."""

		views_payload = self._client.query_analytics(
			ids=settings.youtube_analytics_ids,
			startDate=start_date.isoformat(),
			endDate=end_date.isoformat(),
			metrics="views",
			dimensions="day",
			filters=f"video=={video_database_id}",
		)
		ctr_payload = self._client.query_analytics(
			ids=settings.youtube_analytics_ids,
			startDate=start_date.isoformat(),
			endDate=end_date.isoformat(),
			metrics="impressions,impressionsClickThroughRate,views",
			dimensions="day",
			filters=f"video=={video_database_id}",
		)

		self._view_repository.delete_where(snapshot_id=snapshot.id)
		self._ctr_repository.delete_where(snapshot_id=snapshot.id)

		for index, row in enumerate(views_payload.get("rows", []) or []):
			self._view_repository.create(
				snapshot_id=snapshot.id,
				point_index=index,
				observed_at=parse_iso_datetime(row[0]) or datetime.now(timezone.utc),
				views=int(row[1] or 0),
			)

		for index, row in enumerate(ctr_payload.get("rows", []) or []):
			self._ctr_repository.create(
				snapshot_id=snapshot.id,
				point_index=index,
				elapsed_seconds=index,
				impressions=int(row[1] or 0),
				clicks=0,
				ctr_percent=float(row[2] or 0),
			)

		self._ingest_time_graph(
			"views", "Video Views", views_payload.get("rows", []) or [], snapshot, value_index=1, unit="count"
		)
		self._ingest_time_graph(
			"ctr", "Video CTR", ctr_payload.get("rows", []) or [], snapshot, value_index=2, unit="percent"
		)

	def _collect_retention(self, snapshot: Any, video_database_id: Any, start_date: date, end_date: date) -> None:
		"""Persist retention graph rows for a video snapshot."""

		payload = self._client.query_analytics(
			ids=settings.youtube_analytics_ids,
			startDate=start_date.isoformat(),
			endDate=end_date.isoformat(),
			metrics="audienceWatchRatio",
			dimensions="elapsedVideoTimeRatio",
			filters=f"video=={video_database_id}",
		)
		self._retention_repository.delete_where(snapshot_id=snapshot.id)
		for index, row in enumerate(payload.get("rows", []) or []):
			self._retention_repository.create(
				snapshot_id=snapshot.id,
				point_index=index,
				elapsed_seconds=index,
				retention_percent=float(row[1] or 0),
			)
		anchor = datetime.combine(end_date, time.min, tzinfo=timezone.utc)
		points = [
			GraphPointInput(
				timestamp=anchor + timedelta(seconds=index),
				value=float(row[1] or 0),
				metadata={"elapsed_video_time_ratio": float(row[0] or 0), "point_index": index},
			)
			for index, row in enumerate(payload.get("rows", []) or [])
		]
		self._ingest_graph("retention", "Audience Retention", points, snapshot, "ratio")

	def _ingest_time_graph(
		self,
		graph_type: str,
		name: str,
		rows: list[list[Any]],
		snapshot: Any,
		*,
		value_index: int,
		unit: str,
	) -> None:
		"""Normalize dated Analytics API rows into an immutable graph snapshot."""

		points = [
			GraphPointInput(
				timestamp=parse_iso_datetime(str(row[0])) or datetime.now(timezone.utc),
				value=float(row[value_index] or 0),
				metadata={"point_index": index},
			)
			for index, row in enumerate(rows)
			if len(row) > value_index
		]
		self._ingest_graph(graph_type, name, points, snapshot, unit)

	def _ingest_graph(self, graph_type: str, name: str, points: list[GraphPointInput], snapshot: Any, unit: str) -> None:
		"""Persist graph intelligence in the caller's existing database transaction."""

		self._graph_service.ingest(
			GraphInput(
				graph_type=graph_type,
				name=name,
				points=points,
				channel_id=snapshot.channel_id,
				video_id=snapshot.video_id,
				analytics_snapshot_id=snapshot.id,
				timeframe="custom",
				resolution="daily" if graph_type != "retention" else "curve",
				unit=unit,
				collected_at=snapshot.collected_at,
			)
		)
