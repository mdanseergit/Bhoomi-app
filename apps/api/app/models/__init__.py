"""
SQLAlchemy ORM models for BHOOMI.

Every table follows the convention of `id` (UUID pk), `created_at`,
`updated_at`, and (where soft-deletion is meaningful) `deleted_at`.
"""
from app.models.user import User, Role  # noqa: F401
from app.models.farm import Farm  # noqa: F401
from app.models.soil import SoilProfile, SoilObservation  # noqa: F401
from app.models.crop import CropCycle, CropVariety  # noqa: F401
from app.models.weather import WeatherObservation, WeatherForecast  # noqa: F401
from app.models.satellite import SatelliteObservation  # noqa: F401
from app.models.risk import FarmRiskScore  # noqa: F401
from app.models.advisory import Advisory  # noqa: F401
from app.models.disease import DiseaseScan, DiseaseModel  # noqa: F401
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk  # noqa: F401
from app.models.cooperation import (  # noqa: F401
    StateNode,
    StateDataset,
    DataContract,
    ModelRegistryEntry,
    ModelVersion,
    ModelRequest,
)
from app.models.governance import Consent, DataAccessPolicy, AuditLog  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.system import SystemSetting, AIUsage  # noqa: F401
from app.models.data_network import (  # noqa: F401
    DataProvider,
    ProviderSyncRun,
    RawObservation,
    WaterObservation,
    AgricultureStatistic,
    DataQualityRecord,
    DataConflict,
    FarmDataSnapshot,
    SyncEvent,
)
from app.models.agent import (  # noqa: F401
    AgentSession,
    AgentTask,
    AgentStep,
    ToolExecution,
    AgentMemory,
    AgentAction,
    AgentApproval,
    AgentAlert,
    AgentMonitor,
    AgentEvaluation,
    AgentSessionStatus,
    AgentTaskStatus,
    AgentPhase,
    AgentStepStatus,
    ToolExecutionStatus,
    ToolRiskLevel,
    AgentActionStatus,
    AgentApprovalStatus,
    AgentAlertStatus,
    AgentMonitorStatus,
    AgentMemoryType,
    AgentEvaluationResult,
)
