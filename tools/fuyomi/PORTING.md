# Porting record

Ported from the Fuyomi special workflow in `kucats/vEdit` PR #91 (`27cf1af57a56f784ee61eb08c25ea452c941a85`) plus the related local score-reading follow-up changes present on 2026-09-24: staff pitch recomputation after clef/key corrections, meter changes at system boundaries, notehead grade display with explicit disclaimer, and tests for those behaviors.

The port keeps the workflow, MusicXML/OMR parser, PDF/HTML renderer, browser player, and synthetic tests. It removes the vEdit CLI/package dependency and provides `python -m tools.fuyomi`. Project-specific score data is not embedded in the reusable code. Future reusable fixes should be made here first; keep the vEdit checkout unchanged unless the user explicitly asks for a reverse sync.
