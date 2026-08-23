"""CAREER-OS-V2 foundation package."""

__version__ = "0.1.0"
__all__ = ["CareerPipeline", "PipelineCheckpoint", "PipelineResult", "__version__"]


def __getattr__(name: str):
    """Load the pipeline lazily so lightweight controllers need no pipeline dependencies."""
    if name in {"CareerPipeline", "PipelineCheckpoint", "PipelineResult"}:
        from career_os.pipeline import CareerPipeline, PipelineCheckpoint, PipelineResult

        return {
            "CareerPipeline": CareerPipeline,
            "PipelineCheckpoint": PipelineCheckpoint,
            "PipelineResult": PipelineResult,
        }[name]
    raise AttributeError(name)
