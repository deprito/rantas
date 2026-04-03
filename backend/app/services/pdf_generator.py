"""PDF Report generation service for PhishTrack Statistics Dashboard."""
import io
from datetime import datetime
from pathlib import Path
from typing import Optional

from celery import shared_task

from app.config import settings


REPORTS_DIR = Path(__file__).parent.parent.parent / "reports" / "stats_pdf"


def ensure_reports_dir() -> Path:
    """Ensure the reports directory exists."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def generate_stats_pdf(
    report_id: str,
    stats_data: dict,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> tuple[str, int]:
    """Generate a PDF report with statistics.

    Args:
        report_id: ID of the report record
        stats_data: Dictionary containing all statistics
        start_date: Optional start date filter (ISO format)
        end_date: Optional end date filter (ISO format)

    Returns:
        Tuple of (file_path, file_size_bytes)
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            PageBreak,
        )
    except ImportError:
        raise ImportError("reportlab is required for PDF generation. Install with: pip install reportlab")

    ensure_reports_dir()

    # Generate filename with timestamp
    from app.utils.timezone import now_utc
    timestamp = now_utc().strftime("%Y%m%d_%H%M%S")
    filename = f"phishtrack_stats_{timestamp}.pdf"
    file_path = REPORTS_DIR / filename

    # Create the PDF document
    doc = SimpleDocTemplate(
        str(file_path),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
    )

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.HexColor('#1e3a5f'),
    )
    heading_style = ParagraphStyle(
        'Heading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.HexColor('#2c5282'),
    )
    subheading_style = ParagraphStyle(
        'SubHeading',
        parent=styles['Heading3'],
        fontSize=12,
        spaceAfter=8,
        textColor=colors.HexColor('#4a5568'),
    )

    # Build content
    content = []

    # Title
    content.append(Paragraph("PhishTrack Statistics Report", title_style))

    # Date range
    date_range = "All Time"
    if start_date and end_date:
        date_range = f"{start_date} to {end_date}"
    elif start_date:
        date_range = f"From {start_date}"
    elif end_date:
        date_range = f"Until {end_date}"

    content.append(Paragraph(f"Date Range: {date_range}", styles['Normal']))
    content.append(Paragraph(f"Generated: {now_utc().strftime('%Y-%m-%d %H:%M:%S UTC')}", styles['Normal']))
    content.append(Spacer(1, 20))

    # Overview Section
    content.append(Paragraph("Overview", heading_style))
    overview = stats_data.get('overview', {})
    overview_data = [
        ['Metric', 'Value'],
        ['Total Cases', str(overview.get('total_cases', 0))],
        ['Active Cases', str(overview.get('active_cases', 0))],
        ['Resolved Cases', str(overview.get('resolved_cases', 0))],
        ['Failed Cases', str(overview.get('failed_cases', 0))],
        ['Success Rate', f"{overview.get('success_rate', 0):.1f}%"],
        ['Total Emails Sent', str(overview.get('total_emails_sent', 0))],
        ['Cases Created Today', str(overview.get('cases_created_today', 0))],
        ['Cases Resolved Today', str(overview.get('cases_resolved_today', 0))],
    ]

    avg_resolution = overview.get('average_resolution_time_hours')
    if avg_resolution:
        overview_data.append(['Avg Resolution Time', f"{avg_resolution:.1f} hours"])

    overview_table = Table(overview_data, colWidths=[3 * inch, 2 * inch])
    overview_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7fafc')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    content.append(overview_table)
    content.append(Spacer(1, 20))

    # Status Distribution
    content.append(Paragraph("Status Distribution", heading_style))
    distribution = stats_data.get('status_distribution', {}).get('distribution', [])
    if distribution:
        dist_data = [['Status', 'Count', 'Percentage']]
        for item in distribution:
            dist_data.append([
                item.get('status', 'Unknown'),
                str(item.get('count', 0)),
                f"{item.get('percentage', 0):.1f}%",
            ])
        dist_table = Table(dist_data, colWidths=[2.5 * inch, 1.5 * inch, 1.5 * inch])
        dist_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#38a169')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0fff4')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#c6f6d5')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        content.append(dist_table)
    content.append(Spacer(1, 20))

    # Resolution Metrics
    content.append(Paragraph("Resolution Metrics", heading_style))
    resolution = stats_data.get('resolution_metrics', {})
    if resolution.get('resolved_count', 0) > 0:
        res_data = [
            ['Metric', 'Value'],
            ['Resolved Cases', str(resolution.get('resolved_count', 0))],
        ]
        if resolution.get('average_hours') is not None:
            res_data.append(['Average Time', f"{resolution.get('average_hours'):.1f} hours"])
        if resolution.get('median_hours') is not None:
            res_data.append(['Median Time', f"{resolution.get('median_hours'):.1f} hours"])
        if resolution.get('min_hours') is not None:
            res_data.append(['Fastest Resolution', f"{resolution.get('min_hours'):.1f} hours"])
        if resolution.get('max_hours') is not None:
            res_data.append(['Slowest Resolution', f"{resolution.get('max_hours'):.1f} hours"])

        res_table = Table(res_data, colWidths=[3 * inch, 2 * inch])
        res_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#805ad5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#faf5ff')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9d8fd')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        content.append(res_table)
    else:
        content.append(Paragraph("No resolved cases in the selected period.", styles['Normal']))
    content.append(Spacer(1, 20))

    # Email Effectiveness
    content.append(Paragraph("Email Effectiveness", heading_style))
    email_stats = stats_data.get('email_effectiveness', {})
    email_data = [
        ['Metric', 'Value'],
        ['Total Emails Sent', str(email_stats.get('total_emails_sent', 0))],
        ['Cases with Emails', str(email_stats.get('cases_with_emails', 0))],
        ['Avg Emails per Case', f"{email_stats.get('avg_emails_per_case', 0):.1f}"],
        ['Cases Resolved After Email', str(email_stats.get('cases_resolved_after_email', 0))],
        ['Email Success Rate', f"{email_stats.get('email_success_rate', 0):.1f}%"],
    ]
    email_table = Table(email_data, colWidths=[3 * inch, 2 * inch])
    email_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dd6b20')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fffaf0')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#feebc8')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    content.append(email_table)

    # Page break before tables
    content.append(PageBreak())

    # Top Domains
    content.append(Paragraph("Top Reported Domains", heading_style))
    domains = stats_data.get('top_domains', {}).get('domains', [])
    if domains:
        domain_data = [['Domain', 'Cases', 'Resolved', 'Failed', 'Resolution Rate']]
        for d in domains[:10]:
            domain_data.append([
                d.get('domain', 'Unknown')[:30],
                str(d.get('case_count', 0)),
                str(d.get('resolved_count', 0)),
                str(d.get('failed_count', 0)),
                f"{d.get('resolution_rate', 0):.1f}%",
            ])
        domain_table = Table(domain_data, colWidths=[2 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch, 1.2 * inch])
        domain_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3182ce')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ebf8ff')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bee3f8')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ]))
        content.append(domain_table)
    else:
        content.append(Paragraph("No domain data available.", styles['Normal']))
    content.append(Spacer(1, 20))

    # Top Registrars
    content.append(Paragraph("Top Registrars", heading_style))
    registrars = stats_data.get('top_registrars', {}).get('registrars', [])
    if registrars:
        reg_data = [['Registrar', 'Cases', 'Resolved', 'Resolution Rate', 'Avg Time']]
        for r in registrars[:10]:
            avg_time = r.get('avg_resolution_hours')
            avg_time_str = f"{avg_time:.1f}h" if avg_time else "N/A"
            reg_data.append([
                r.get('registrar', 'Unknown')[:25],
                str(r.get('case_count', 0)),
                str(r.get('resolved_count', 0)),
                f"{r.get('resolution_rate', 0):.1f}%",
                avg_time_str,
            ])
        reg_table = Table(reg_data, colWidths=[2.2 * inch, 0.7 * inch, 0.8 * inch, 1 * inch, 0.9 * inch])
        reg_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#319795')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e6fffa')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#b2f5ea')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ]))
        content.append(reg_table)
    else:
        content.append(Paragraph("No registrar data available.", styles['Normal']))

    # Footer
    content.append(Spacer(1, 40))
    content.append(Paragraph(
        "Generated by PhishTrack Automated Takedown System",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.gray),
    ))

    # Build PDF
    doc.build(content)

    # Get file size
    file_size = file_path.stat().st_size

    return str(file_path), file_size


@shared_task(name="generate_stats_pdf")
def generate_stats_pdf_task(
    report_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Celery task to generate a statistics PDF report.

    Args:
        report_id: ID of the report record to update
        start_date: Optional start date filter (ISO format)
        end_date: Optional end date filter (ISO format)

    Returns:
        Dictionary with result information
    """
    from app.database import get_sync_db_context
    from app.models import GeneratedReport, Case
    from sqlalchemy import select, func

    report = None

    try:
        with get_sync_db_context() as db:
            # Get report record
            report = db.execute(select(GeneratedReport).where(GeneratedReport.id == report_id)).scalar_one_or_none()
            if not report:
                return {"error": f"Report {report_id} not found"}

            # Parse dates
            start_dt = None
            end_dt = None
            if start_date:
                start_dt = datetime.fromisoformat(start_date)
            if end_date:
                end_dt = datetime.fromisoformat(end_date)

            # Collect all stats data
            stats_data = {}

            # Build base query with date filters
            def apply_date_filters(query):
                if start_dt:
                    query = query.where(Case.created_at >= start_dt)
                if end_dt:
                    query = query.where(Case.created_at <= end_dt)
                return query

            # Overview stats
            total_result = db.execute(
                apply_date_filters(select(func.count(Case.id)))
            )
            total_cases = total_result.scalar() or 0

            status_result = db.execute(
                apply_date_filters(
                    select(Case.status, func.count(Case.id)).group_by(Case.status)
                )
            )
            status_counts = dict(status_result.all())

            resolved = status_counts.get("RESOLVED", 0)
            failed = status_counts.get("FAILED", 0)
            active = sum(c for s, c in status_counts.items() if s not in ["RESOLVED", "FAILED"])
            terminal = resolved + failed
            success_rate = (resolved / terminal * 100) if terminal > 0 else 0

            emails_result = db.execute(
                apply_date_filters(select(func.sum(Case.emails_sent)))
            )
            total_emails = emails_result.scalar() or 0

            stats_data['overview'] = {
                'total_cases': total_cases,
                'active_cases': active,
                'resolved_cases': resolved,
                'failed_cases': failed,
                'success_rate': success_rate,
                'total_emails_sent': total_emails,
                'cases_created_today': 0,
                'cases_resolved_today': 0,
            }

            # Status distribution
            distribution = []
            for status_val, count in status_counts.items():
                pct = (count / total_cases * 100) if total_cases > 0 else 0
                distribution.append({
                    'status': status_val,
                    'count': count,
                    'percentage': pct,
                })
            stats_data['status_distribution'] = {
                    'distribution': distribution,
                    'total': total_cases,
                }

            # Resolution metrics
            resolved_cases_result = db.execute(
                apply_date_filters(
                    select(Case).where(Case.status == "RESOLVED")
                )
            )
            resolved_cases = resolved_cases_result.scalars().all()

            res_times = []
            for c in resolved_cases:
                if c.created_at and c.updated_at:
                    delta = c.updated_at - c.created_at
                    hours = delta.total_seconds() / 3600
                    res_times.append(hours)

            if res_times:
                res_times.sort()
                n = len(res_times)
                median = res_times[n // 2] if n % 2 == 1 else (res_times[n // 2 - 1] + res_times[n // 2]) / 2
                stats_data['resolution_metrics'] = {
                    'average_hours': sum(res_times) / n,
                    'median_hours': median,
                    'min_hours': res_times[0],
                    'max_hours': res_times[-1],
                    'resolved_count': len(resolved_cases),
                }
            else:
                stats_data['resolution_metrics'] = {'resolved_count': 0}

            # Email effectiveness
            all_cases_result = db.execute(apply_date_filters(select(Case)))
            all_cases = all_cases_result.scalars().all()

            total_emails_sent = 0
            cases_with_emails = 0
            cases_resolved_after_email = 0
            for c in all_cases:
                if c.emails_sent > 0:
                    total_emails_sent += c.emails_sent
                    cases_with_emails += 1
                    if c.status == "RESOLVED":
                        cases_resolved_after_email += 1

            avg_per_case = total_emails_sent / cases_with_emails if cases_with_emails > 0 else 0
            email_success = (cases_resolved_after_email / cases_with_emails * 100) if cases_with_emails > 0 else 0

            stats_data['email_effectiveness'] = {
                'total_emails_sent': total_emails_sent,
                'cases_with_emails': cases_with_emails,
                'avg_emails_per_case': avg_per_case,
                'cases_resolved_after_email': cases_resolved_after_email,
                'email_success_rate': email_success,
            }

            # Top domains
            from urllib.parse import urlparse
            domain_stats = {}
            for c in all_cases:
                try:
                    parsed = urlparse(c.url)
                    domain = parsed.netloc or parsed.path
                    if domain.startswith("www."):
                        domain = domain[4:]
                except:
                    domain = c.url

                if domain not in domain_stats:
                    domain_stats[domain] = {'case_count': 0, 'resolved_count': 0, 'failed_count': 0}
                domain_stats[domain]['case_count'] += 1
                if c.status == "RESOLVED":
                    domain_stats[domain]['resolved_count'] += 1
                elif c.status == "FAILED":
                    domain_stats[domain]['failed_count'] += 1

            domains_list = []
            for domain, st in domain_stats.items():
                total_term = st['resolved_count'] + st['failed_count']
                rate = (st['resolved_count'] / total_term * 100) if total_term > 0 else 0
                domains_list.append({
                    'domain': domain,
                    'case_count': st['case_count'],
                    'resolved_count': st['resolved_count'],
                    'failed_count': st['failed_count'],
                    'resolution_rate': rate,
                })
            domains_list.sort(key=lambda x: x['case_count'], reverse=True)
            stats_data['top_domains'] = {'domains': domains_list[:10], 'total': len(domain_stats)}

            # Top registrars
            registrar_stats = {}
            for c in all_cases:
                registrar = "Unknown"
                if isinstance(c.domain_info, dict):
                    registrar = c.domain_info.get("registrar") or "Unknown"

                if registrar not in registrar_stats:
                    registrar_stats[registrar] = {'case_count': 0, 'resolved_count': 0, 'total_hours': 0}
                registrar_stats[registrar]['case_count'] += 1
                if c.status == "RESOLVED":
                    registrar_stats[registrar]['resolved_count'] += 1
                    if c.created_at and c.updated_at:
                        delta = c.updated_at - c.created_at
                        registrar_stats[registrar]['total_hours'] += delta.total_seconds() / 3600

            registrars_list = []
            for reg, st in registrar_stats.items():
                rate = (st['resolved_count'] / st['case_count'] * 100) if st['case_count'] > 0 else 0
                avg_h = (st['total_hours'] / st['resolved_count']) if st['resolved_count'] > 0 else None
                registrars_list.append({
                    'registrar': reg,
                    'case_count': st['case_count'],
                    'resolved_count': st['resolved_count'],
                    'resolution_rate': rate,
                    'avg_resolution_hours': avg_h,
                })
            registrars_list.sort(key=lambda x: x['case_count'], reverse=True)
            stats_data['top_registrars'] = {'registrars': registrars_list[:10], 'total': len(registrar_stats)}

            # Generate PDF
            file_path, file_size = generate_stats_pdf(
                report_id,
                stats_data,
                start_date,
                end_date,
            )

            # Update report record
            report.file_path = file_path
            report.file_size_bytes = file_size
            report.status = "completed"
            report.cases_count = total_cases
            db.commit()

            return {
                "success": True,
                "file_path": file_path,
                "file_size": file_size,
            }

    except Exception as e:
        # Update report with error
        if report:
            report.status = "failed"
            report.error_message = str(e)[:1000]
            db.commit()
        return {"error": str(e)}
