"""CAREER-OS-V2 foundation package."""

__version__ = "0.1.0"

from career_os.pipeline import CareerPipeline, PipelineCheckpoint, PipelineResult

__all__ = ["CareerPipeline", "PipelineCheckpoint", "PipelineResult", "__version__"]
