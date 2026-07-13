"""Module 6b: plots + final markdown report assembly."""

from pathlib import Path
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")  # headless - this pipeline runs as a batch script, never in a GUI context
import matplotlib.pyplot as plt

from analysis.resolution_sensitivity import config
from analysis.resolution_sensitivity.convergence import ConvergenceMetrics
from analysis.resolution_sensitivity.input_resolution import InputResolutionCeiling
from analysis.resolution_sensitivity.maup_offset import OffsetStabilityResult


def plot_convergence(metrics: List[ConvergenceMetrics], mad_threshold: float, output_path: Path) -> None:
    labels = [f"{m.coarse_resolution_m:.0f}m vs {m.fine_resolution_m:.0f}m" for m in metrics]
    mads = [m.mad for m in metrics]
    rhos = [m.spearman_rho for m in metrics]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    ax1.plot(labels, mads, marker="o", color="#dc2626")
    ax1.axhline(mad_threshold, color="gray", linestyle="--", label=f"yakınsama eşiği ({mad_threshold})")
    ax1.set_ylabel("Ortalama Mutlak Fark (MAD)")
    ax1.set_title("Çözünürlükler Arası Skor Farkı")
    ax1.legend()
    ax1.tick_params(axis="x", rotation=30)

    ax2.plot(labels, rhos, marker="o", color="#2563eb")
    ax2.set_ylim(0, 1.02)
    ax2.set_ylabel("Spearman sıralama korelasyonu")
    ax2.set_title("Büyüme Sıralamasının Korunumu")
    ax2.tick_params(axis="x", rotation=30)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_offset_stability(results: List[OffsetStabilityResult], threshold: float, output_path: Path) -> None:
    resolutions = [r.resolution_m for r in results]
    p90 = [r.p90_std for r in results]

    fig, ax = plt.subplots(figsize=(6, 4.5))
    colors = ["#dc2626" if r.p90_std >= threshold else "#16a34a" for r in results]
    ax.bar([str(int(r)) for r in resolutions], p90, color=colors)
    ax.axhline(threshold, color="gray", linestyle="--", label=f"kararsızlık eşiği ({threshold})")
    ax.set_xlabel("Izgara çözünürlüğü (m)")
    ax.set_ylabel("p90 değişim katsayısı (offset başına)")
    ax.set_title("MAUP Ofset Kararlılığı (kırmızı = kararsız)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _format_grid_stats_table(grid_stats_df) -> str:
    lines = ["| Çözünürlük (m) | Hücre Sayısı | Üretim Süresi (s) |", "|---|---|---|"]
    for _, row in grid_stats_df.iterrows():
        lines.append(f"| {row['resolution_m']:.0f} | {row['cell_count']:,} | {row['generation_seconds']:.2f} |")
    return "\n".join(lines)


def _format_convergence_table(metrics: List[ConvergenceMetrics]) -> str:
    lines = [
        "| Karşılaştırma | Ortak Hücre | MAD | Spearman ρ | Kappa |",
        "|---|---|---|---|---|",
    ]
    for m in metrics:
        lines.append(
            f"| {m.coarse_resolution_m:.0f}m ↔ {m.fine_resolution_m:.0f}m | {m.n_compared_cells:,} | "
            f"{m.mad:.4f} | {m.spearman_rho:.4f} | {m.kappa:.4f} |"
        )
    return "\n".join(lines)


def _format_offset_table(results: List[OffsetStabilityResult]) -> str:
    if not results:
        return "(Bu çalıştırmada MAUP ofset kontrolü atlandı - `--skip-maup`.)"
    lines = [
        "| Çözünürlük (m) | Test Edilen Ofset | Ortalama CV | p90 CV | Durum |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        status = "KARARLI" if r.is_stable else "KARARSIZ (ızgaraya bağımlı)"
        lines.append(
            f"| {r.resolution_m:.0f} | {r.offsets_tested} | {r.mean_std:.4f} | {r.p90_std:.4f} | {status} |"
        )
    return "\n".join(lines)


def _format_adaptive_section(adaptive_stats: dict) -> str:
    if not adaptive_stats:
        return "(Bu çalıştırmada uyarlanabilir ızgara adımı atlandı - `--skip-adaptive`.)"
    return (
        f"- Başlangıç kaba çözünürlük: {adaptive_stats['n_coarse_cells_at_start']:,} hücre (1000 m)\n"
        f"- Üst seviyede bölünen hücre sayısı: {adaptive_stats['n_split_at_top_level']:,}\n"
        f"- Nihai (uyarlanabilir) hücre sayısı: {adaptive_stats['n_leaves']:,}\n"
        f"- Aynı alanı düzenli en-ince ızgarayla kaplasaydık gereken hücre sayısı: "
        f"{adaptive_stats['uniform_fine_grid_equivalent_cells']:,}\n"
        f"- **Tasarruf oranı: {adaptive_stats['savings_factor']:.2f}x**"
    )


def _format_input_ceiling_table(ceilings: List[InputResolutionCeiling]) -> str:
    lines = ["| Girdi Katmanı | Çözünürlük / Kapsam |", "|---|---|"]
    for c in ceilings:
        lines.append(f"| {c.layer_name} | {c.ceiling_description} |")
    return "\n".join(lines)


def generate_markdown_report(
    *,
    profile_name: str,
    grid_stats_df,
    convergence_metrics: List[ConvergenceMetrics],
    convergence_resolution_m: Optional[float],
    mad_threshold: float,
    offset_results: List[OffsetStabilityResult],
    adaptive_stats: dict,
    mahalle_ceiling: InputResolutionCeiling,
    vector_layer_notes: List[InputResolutionCeiling],
    unavailable_layers: List[InputResolutionCeiling],
    resolution_warnings: List[str],
) -> str:
    offset_by_resolution = {r.resolution_m: r for r in offset_results}
    convergence_is_unstable = (
        convergence_resolution_m is not None
        and convergence_resolution_m in offset_by_resolution
        and not offset_by_resolution[convergence_resolution_m].is_stable
    )
    convergence_below_data_ceiling = (
        convergence_resolution_m is not None
        and mahalle_ceiling.effective_linear_resolution_m is not None
        and convergence_resolution_m < mahalle_ceiling.effective_linear_resolution_m
    )

    if convergence_resolution_m is None:
        recommendation = (
            "Test edilen çözünürlüklerin hiçbiri yakınsama eşiğinin altına inmedi - "
            "modelin en ince test edilen çözünürlükte (bkz. tablo) bile hâlâ anlamlı ölçüde "
            "değiştiği görülüyor; daha ince bir ızgara test edilmeden kesin bir öneri verilemez."
        )
    elif not convergence_is_unstable and not convergence_below_data_ceiling:
        recommendation = (
            f"Sakarya için değerleme amaçlı ideal DÜZENLİ ızgara çözünürlüğü ≈ "
            f"**{convergence_resolution_m:.0f} m**, çünkü bunun ötesinde inceltmenin MAD'ı "
            f"{mad_threshold} eşiğinin altına düşüyor (yakınsadı), bu çözünürlük ızgara "
            f"hizasından bağımsız (MAUP-kararlı) ve gerçek veri tavanının üzerinde kalıyor - "
            f"daha ince bir ızgara hesap maliyetini artırıp gerçek doğruluğu iyileştirmiyor."
        )
    else:
        reasons = []
        if convergence_is_unstable:
            reasons.append(
                f"{convergence_resolution_m:.0f} m'nin kendisi MAUP ofset testinde KARARSIZ çıktı "
                f"(p90 değişim katsayısı {offset_by_resolution[convergence_resolution_m].p90_std:.4f}, "
                f"eşik {config.MAUP_INSTABILITY_STD_THRESHOLD:.4f}) - yani bu çözünürlükte bir hücrenin "
                f"skoru kısmen ızgaranın rastgele hizasından geliyor"
            )
        if convergence_below_data_ceiling:
            reasons.append(
                f"{convergence_resolution_m:.0f} m, mahalle-poligon verisinin gerçek çözünürlük tavanının "
                f"(~{mahalle_ceiling.effective_linear_resolution_m:.0f} m) zaten altında - nüfus artışı/"
                f"momentum/büyüme yönü faktörleri için bu ölçekte sahte detay üretiliyor"
            )
        recommendation = (
            f"Yakınsama testi tek başına {convergence_resolution_m:.0f} m'yi yeterli gösteriyor "
            f"(MAD < {mad_threshold}), ANCAK bu çözünürlük iki ayrı sorunla sakıncalı: "
            f"{'; '.join(reasons)}. Bu yüzden {convergence_resolution_m:.0f} m TEK BAŞINA yeterli "
            f"bir öneri değildir - test edilen ızgara merdiveni ({', '.join(f'{r:.0f}m' for r in offset_by_resolution)}) "
            f"içinde hem MAUP-kararlı hem yakınsamış bir çözünürlük bulunuyorsa (bkz. tablo 2 ve 3) "
            f"onun tercih edilmesi, bulunmuyorsa ~{mahalle_ceiling.effective_linear_resolution_m:.0f} m "
            f"civarında, bu ladderin dışında daha kaba bir çözünürlüğün ayrıca test edilmesi önerilir."
        )

    unstable_resolutions = [r.resolution_m for r in offset_results if not r.is_stable]
    if not offset_results:
        maup_note = "(MAUP ofset kontrolü bu çalıştırmada atlandı.)"
    elif unstable_resolutions:
        maup_note = (
            f"**Dikkat**: {', '.join(f'{r:.0f}m' for r in unstable_resolutions)} çözünürlük(ler)i "
            f"ızgaranın nereden başladığına duyarlı (MAUP kararsızlığı) - bu çözünürlüklerde bir "
            f"hücrenin skoru kısmen gerçek konumundan değil, ızgaranın rastgele hizasından geliyor."
        )
    else:
        maup_note = "Test edilen tüm çözünürlükler ızgara hizasından bağımsız (kararlı) çıktı."

    offset_plot_block = "![Ofset kararlılığı](offset_stability.png)" if offset_results else ""
    warnings_block = "\n".join(f"- {w}" for w in resolution_warnings) if resolution_warnings else "- (Yok)"

    return f"""# Sakarya Kentsel Büyüme Modeli - Çözünürlük Duyarlılık Analizi

Profil: **{profile_name}**

## 1. Çok-Çözünürlüklü Izgara Üretimi

{_format_grid_stats_table(grid_stats_df)}

## 2. Yakınsama Analizi

{_format_convergence_table(convergence_metrics)}

![Yakınsama grafiği](convergence.png)

Yakınsama eşiği: MAD < {mad_threshold}

## 3. MAUP Ofset (Hiza) Kararlılığı

{_format_offset_table(offset_results)}

{offset_plot_block}

{maup_note}

## 4. Uyarlanabilir (Quadtree) Izgara

{_format_adaptive_section(adaptive_stats)}

## 5. Girdi Verisi Çözünürlük Tavanı

### Mahalle/nüfus tabanlı faktörler (nüfus artışı, momentum, büyüme yönü)
{mahalle_ceiling.ceiling_description}

### Nokta/vektör tabanlı faktörler (OSM kaynaklı)
{_format_input_ceiling_table(vector_layer_notes)}

### Bu projede BULUNMAYAN katmanlar
{_format_input_ceiling_table(unavailable_layers)}

### Çözünürlük Uyarıları
{warnings_block}

## 6. SONUÇ

{recommendation}
"""
