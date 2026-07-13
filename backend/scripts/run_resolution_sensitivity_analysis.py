"""Sakarya kentsel büyüme modeli için çözünürlük duyarlılık testi ve
uyarlanabilir ızgara hattı.

Bu, gerçek üretim skorlama motorunu (CompositeHeatmapScorer + gerçek
ingest edilmiş OSM/belediye verisi) kullanır - yer tutucu bir skorlama
fonksiyonu YOKTUR.

Kullanım (backend/ dizininden):

    python scripts/run_resolution_sensitivity_analysis.py
    python scripts/run_resolution_sensitivity_analysis.py --include-100m
    python scripts/run_resolution_sensitivity_analysis.py --resolutions 1000 500
    python scripts/run_resolution_sensitivity_analysis.py --skip-maup --skip-adaptive
    python scripts/run_resolution_sensitivity_analysis.py --profile industrial

100m çözünürlük varsayılan olarak ÇALIŞTIRILMAZ - tam ızgara skorlaması
(MAUP kontrolü hariç, o modül zaten sadece prob noktalarını skorluyor)
580.000+ hücre gerektirir ve gerçek ölçümlere göre ~5-6 dakika sürer;
--include-100m ile açıkça istenmelidir.
"""

import argparse
import sys
from pathlib import Path

# Windows consoles default to a legacy codepage (e.g. cp1254) that can't
# encode the arrow/unicode characters this pipeline's progress output
# uses - reconfigure stdout to UTF-8 up front rather than avoiding those
# characters everywhere (matches the fix already used elsewhere in this
# project for the same class of Windows console issue).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.entities.land_use_profile import LandUseProfile  # noqa: E402
from app.infrastructure.persistence.database import SessionLocal  # noqa: E402
from analysis.resolution_sensitivity import config  # noqa: E402
from analysis.resolution_sensitivity.pipeline import run  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--resolutions", type=float, nargs="+", default=None,
        help=f"Test edilecek hücre boyutları (metre). Varsayılan: {config.DEFAULT_RESOLUTIONS_M}",
    )
    parser.add_argument(
        "--include-100m", action="store_true",
        help="100m'yi de çözünürlük listesine ekle (varsayılan listede yok - bkz modül docstring'i)",
    )
    parser.add_argument(
        "--profile", type=str, default="balanced", choices=[p.value for p in LandUseProfile],
        help="Hangi arazi kullanım profiliyle skorlanacağı (varsayılan: balanced)",
    )
    parser.add_argument("--skip-maup", action="store_true", help="MAUP ofset kararlılık testini atla")
    parser.add_argument("--skip-adaptive", action="store_true", help="Uyarlanabilir ızgara adımını atla")
    parser.add_argument(
        "--calibration-sample", type=int, default=500,
        help="Süre tahmini için kaç hücrelik örnekle kalibrasyon yapılacağı",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    resolutions = args.resolutions if args.resolutions else list(config.DEFAULT_RESOLUTIONS_M)
    if args.include_100m and 100 not in resolutions:
        resolutions.append(100)

    profile = LandUseProfile(args.profile)

    session = SessionLocal()
    try:
        run(
            session,
            resolutions_m=resolutions,
            profile=profile,
            run_maup_offset_check=not args.skip_maup,
            run_adaptive_grid=not args.skip_adaptive,
            scoring_calibration_sample=args.calibration_sample,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
