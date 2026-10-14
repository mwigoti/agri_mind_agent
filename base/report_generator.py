"""
Agrivision Report Generator
Generates PDF and DOCX reports from analysis results
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend
import io
from datetime import datetime
import numpy as np


class AgrivisionReportGenerator:
    """
    Generate comprehensive agricultural analysis reports
    """
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2E7D32'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        # Section header
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1B5E20'),
            spaceAfter=12,
            spaceBefore=12
        ))
        
        # Subsection header
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading3'],
            fontSize=14,
            textColor=colors.HexColor('#388E3C'),
            spaceAfter=6
        ))
    
    def generate_pdf_report(self, analysis_data: dict, 
                           include_maps: bool = True,
                           include_charts: bool = True) -> io.BytesIO:
        """
        Generate PDF report
        
        Args:
            analysis_data: Complete analysis results
            include_maps: Include map visualizations
            include_charts: Include charts and graphs
            
        Returns:
            BytesIO buffer with PDF content
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        
        # Title page
        story.extend(self._create_title_page(analysis_data))
        story.append(PageBreak())
        
        # Executive summary
        story.extend(self._create_executive_summary(analysis_data))
        story.append(PageBreak())
        
        # Field information
        story.extend(self._create_field_info_section(analysis_data))
        story.append(Spacer(1, 0.3*inch))
        
        # Health assessment
        story.extend(self._create_health_section(analysis_data))
        story.append(Spacer(1, 0.3*inch))
        
        # Yield prediction
        story.extend(self._create_yield_section(analysis_data))
        story.append(PageBreak())
        
        # Vegetation indices
        story.extend(self._create_indices_section(analysis_data))
        story.append(Spacer(1, 0.3*inch))
        
        # Soil and weather
        story.extend(self._create_environmental_section(analysis_data))
        story.append(PageBreak())
        
        # Recommendations
        story.extend(self._create_recommendations_section(analysis_data))
        
        # Charts
        if include_charts:
            story.append(PageBreak())
            story.extend(self._create_charts_section(analysis_data))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def generate_docx_report(self, analysis_data: dict,
                            include_maps: bool = True,
                            include_charts: bool = True) -> io.BytesIO:
        """
        Generate DOCX report
        
        Args:
            analysis_data: Complete analysis results
            include_maps: Include map visualizations
            include_charts: Include charts and graphs
            
        Returns:
            BytesIO buffer with DOCX content
        """
        doc = Document()
        
        # Set default font
        style = doc.styles['Normal']
        font = style.font
        font.name = 'Calibri'
        font.size = Pt(11)
        
        # Title page
        self._add_docx_title_page(doc, analysis_data)
        doc.add_page_break()
        
        # Executive summary
        self._add_docx_executive_summary(doc, analysis_data)
        doc.add_page_break()
        
        # Field information
        self._add_docx_field_info(doc, analysis_data)
        
        # Health assessment
        self._add_docx_health_section(doc, analysis_data)
        
        # Yield prediction
        self._add_docx_yield_section(doc, analysis_data)
        doc.add_page_break()
        
        # Indices
        self._add_docx_indices_section(doc, analysis_data)
        
        # Environmental data
        self._add_docx_environmental_section(doc, analysis_data)
        doc.add_page_break()
        
        # Recommendations
        self._add_docx_recommendations(doc, analysis_data)
        
        # Save to buffer
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        return buffer
    
    # PDF Report Sections
    
    def _create_title_page(self, data: dict) -> list:
        """Create title page elements"""
        elements = []
        
        # Title
        title = Paragraph("AGRIVISION", self.styles['CustomTitle'])
        elements.append(title)
        elements.append(Spacer(1, 0.2*inch))
        
        subtitle = Paragraph("Agricultural Analysis Report", self.styles['Heading2'])
        elements.append(subtitle)
        elements.append(Spacer(1, 0.5*inch))
        
        # Field information
        field_info = data['field_information']
        info_text = f"""
        <b>Field:</b> {field_info['name']}<br/>
        <b>Crop Type:</b> {field_info['crop_type'].title()}<br/>
        <b>Growth Stage:</b> {field_info['growth_stage'].replace('_', ' ').title()}<br/>
        <b>Area:</b> {field_info.get('area_hectares', 0):.2f} hectares<br/>
        <b>Report Date:</b> {data['analysis_date']}
        """
        info_para = Paragraph(info_text, self.styles['Normal'])
        elements.append(info_para)
        
        elements.append(Spacer(1, 1*inch))
        
        # Overall health indicator
        health = data['health_assessment']
        health_color = self._get_health_color(health['overall_health'])
        
        health_text = f"""
        <para align=center>
        <b><font size=20 color={health_color}>
        Overall Health Score: {health['overall_health']:.1f}%
        </font></b><br/>
        <font size=14>{health['health_category']}</font>
        </para>
        """
        elements.append(Paragraph(health_text, self.styles['Normal']))
        
        return elements
    
    def _create_executive_summary(self, data: dict) -> list:
        """Create executive summary"""
        elements = []
        
        elements.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.2*inch))
        
        health = data['health_assessment']
        yield_pred = data['yield_prediction']
        field_info = data['field_information']
        
        summary_text = f"""
        This report presents a comprehensive analysis of <b>{field_info['name']}</b>, 
        a {field_info.get('area_hectares', 0):.2f}-hectare field cultivating 
        <b>{field_info['crop_type'].title()}</b> currently in the 
        <b>{field_info['growth_stage'].replace('_', ' ')}</b> stage.
        <br/><br/>
        <b>Key Findings:</b><br/>
        • Overall crop health is assessed as <b>{health['health_category']}</b> 
        with a score of {health['overall_health']:.1f}%<br/>
        • Predicted yield: <b>{yield_pred['predicted_yield_tonnes_per_ha']:.2f} tonnes/ha</b>
        ({yield_pred['yield_category']})<br/>
        • Vegetation health: {health['vegetation_health']:.1f}%<br/>
        • Water stress index: {health['water_stress_index']:.1f}%<br/>
        • Soil health: {health['soil_health']:.1f}%<br/>
        <br/>
        The analysis identifies <b>{len(yield_pred.get('limiting_factors', []))} 
        limiting factor(s)</b> affecting yield potential. With targeted interventions, 
        yield could potentially increase to <b>
        {yield_pred['optimization_potential']['achievable_yield']:.2f} tonnes/ha</b>.
        """
        
        elements.append(Paragraph(summary_text, self.styles['BodyText']))
        
        return elements
    
    def _create_field_info_section(self, data: dict) -> list:
        """Create field information section"""
        elements = []
        
        elements.append(Paragraph("Field Information", self.styles['SectionHeader']))
        
        field_info = data['field_information']
        
        # Create table
        table_data = [
            ['Property', 'Value'],
            ['Field Name', field_info['name']],
            ['Crop Type', field_info['crop_type'].title()],
            ['Growth Stage', field_info['growth_stage'].replace('_', ' ').title()],
            ['Area', f"{field_info.get('area_hectares', 0):.2f} hectares"],
            ['Analysis Date', data['analysis_date']]
        ]
        
        table = Table(table_data, colWidths=[2.5*inch, 3.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        
        return elements
    
    def _create_health_section(self, data: dict) -> list:
        """Create health assessment section"""
        elements = []
        
        elements.append(Paragraph("Crop Health Assessment", self.styles['SectionHeader']))
        
        health = data['health_assessment']
        
        # Health scores table
        table_data = [
            ['Metric', 'Score (%)', 'Category'],
            ['Overall Health', f"{health['overall_health']:.1f}", health['health_category']],
            ['Vegetation Health', f"{health['vegetation_health']:.1f}", 
             self._categorize_score(health['vegetation_health'])],
            ['Water Stress Index', f"{health['water_stress_index']:.1f}",
             self._categorize_score(100 - health['water_stress_index'])],
            ['Soil Health', f"{health['soil_health']:.1f}",
             self._categorize_score(health['soil_health'])],
            ['Weather Favorability', f"{health['weather_favorability']:.1f}",
             self._categorize_score(health['weather_favorability'])]
        ]
        
        table = Table(table_data, colWidths=[2.5*inch, 1.5*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B5E20')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#E8F5E9')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F8E9')])
        ]))
        
        elements.append(table)
        
        return elements
    
    def _create_yield_section(self, data: dict) -> list:
        """Create yield prediction section"""
        elements = []
        
        elements.append(Paragraph("Yield Prediction & Optimization", self.styles['SectionHeader']))
        
        yield_data = data['yield_prediction']
        opt = yield_data['optimization_potential']
        
        # Main prediction
        pred_text = f"""
        <b>Predicted Yield:</b> {yield_data['predicted_yield_tonnes_per_ha']:.2f} tonnes/ha<br/>
        <b>Confidence Level:</b> {yield_data['confidence_percentage']}%<br/>
        <b>Yield Category:</b> {yield_data['yield_category']}<br/>
        <b>LAI Estimate:</b> {yield_data['lai_estimate']:.2f}
        """
        elements.append(Paragraph(pred_text, self.styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Optimization potential
        elements.append(Paragraph("Optimization Potential", self.styles['SubsectionHeader']))
        
        opt_table = [
            ['Metric', 'Value (tonnes/ha)'],
            ['Current Predicted Yield', f"{opt['current_yield']:.2f}"],
            ['Optimal Yield (100%)', f"{opt['optimal_yield']:.2f}"],
            ['Yield Gap', f"{opt['gap_tonnes_per_ha']:.2f}"],
            ['Achievable Yield (70% optimization)', f"{opt['achievable_yield']:.2f}"],
            ['Total Potential Gain', f"{opt['total_potential_gain']:.2f}"]
        ]
        
        table = Table(opt_table, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F8E9')])
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Limiting factors
        if yield_data.get('limiting_factors'):
            elements.append(Paragraph("Limiting Factors", self.styles['SubsectionHeader']))
            factors_text = "<br/>".join([f"• {factor}" for factor in yield_data['limiting_factors']])
            elements.append(Paragraph(factors_text, self.styles['Normal']))
        
        return elements
    
    def _create_indices_section(self, data: dict) -> list:
        """Create vegetation indices section"""
        elements = []
        
        elements.append(Paragraph("Vegetation Indices", self.styles['SectionHeader']))
        
        indices = data['vegetation_indices']
        
        # Main indices
        main_indices = ['NDVI', 'EVI', 'SAVI', 'NDWI', 'NDMI', 'GNDVI']
        table_data = [['Index', 'Value', 'Interpretation']]
        
        for idx in main_indices:
            if idx in indices:
                value = indices[idx]
                interp = self._interpret_index(idx, value)
                table_data.append([idx, f"{value:.3f}", interp])
        
        table = Table(table_data, colWidths=[1.5*inch, 1.5*inch, 3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1B5E20')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F1F8E9')])
        ]))
        
        elements.append(table)
        
        return elements
    
    def _create_environmental_section(self, data: dict) -> list:
        """Create soil and weather section"""
        elements = []
        
        elements.append(Paragraph("Environmental Conditions", self.styles['SectionHeader']))
        
        # Soil data
        elements.append(Paragraph("Soil Properties", self.styles['SubsectionHeader']))
        soil = data['soil_analysis']
        
        soil_table = [
            ['Property', 'Value', 'Status'],
            ['pH', f"{soil.get('ph', 0):.1f}", self._soil_ph_status(soil.get('ph', 7))],
            ['Moisture', f"{soil.get('moisture', 0):.2f}", 'Field data'],
            ['Nitrogen (mg/kg)', f"{soil.get('nitrogen', 0):.1f}", 
             self._nutrient_status(soil.get('nitrogen', 0), 'N')],
            ['Phosphorus (mg/kg)', f"{soil.get('phosphorus', 0):.1f}",
             self._nutrient_status(soil.get('phosphorus', 0), 'P')],
            ['Potassium (mg/kg)', f"{soil.get('potassium', 0):.1f}",
             self._nutrient_status(soil.get('potassium', 0), 'K')],
            ['Organic Matter (%)', f"{soil.get('organic_matter', 0):.1f}",
             self._om_status(soil.get('organic_matter', 0))]
        ]
        
        table = Table(soil_table, colWidths=[2*inch, 1.5*inch, 2.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#795548')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#EFEBE9')])
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Weather data
        elements.append(Paragraph("Weather Conditions", self.styles['SubsectionHeader']))
        weather = data['weather_data']
        
        weather_table = [
            ['Parameter', 'Value'],
            ['Temperature (°C)', f"{weather.get('temperature', 0):.1f}"],
            ['7-Day Rainfall (mm)', f"{weather.get('rainfall_7day', 0):.1f}"],
            ['Humidity (%)', f"{weather.get('humidity', 0):.1f}"]
        ]
        
        table = Table(weather_table, colWidths=[2.5*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976D2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#E3F2FD')])
        ]))
        
        elements.append(table)
        
        return elements
    
    def _create_recommendations_section(self, data: dict) -> list:
        """Create recommendations section"""
        elements = []
        
        elements.append(Paragraph("Management Recommendations", self.styles['SectionHeader']))
        
        recommendations = data['health_assessment']['recommendations']
        
        for i, rec in enumerate(recommendations, 1):
            # Priority badge
            priority_color = {
                'Critical': '#D32F2F',
                'High': '#F57C00',
                'Medium': '#FBC02D',
                'Low': '#388E3C'
            }.get(rec['priority'], '#757575')
            
            rec_text = f"""
            <b><font color={priority_color}>
            [{rec['priority']}]</font> {rec['category']}</b><br/>
            <b>Issue:</b> {rec['issue']}<br/>
            <b>Recommended Action:</b> {rec['action']}<br/>
            <b>Expected Impact:</b> {rec['expected_improvement']}
            """
            
            elements.append(Paragraph(rec_text, self.styles['Normal']))
            elements.append(Spacer(1, 0.15*inch))
        
        return elements
    
    def _create_charts_section(self, data: dict) -> list:
        """Create charts section"""
        elements = []
        
        elements.append(Paragraph("Visual Analysis", self.styles['SectionHeader']))
        
        # Health scores chart
        health = data['health_assessment']
        fig = self._create_health_chart(health)
        img_buffer = io.BytesIO()
        fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
        img_buffer.seek(0)
        img = Image(img_buffer, width=5*inch, height=3*inch)
        elements.append(img)
        plt.close(fig)
        
        return elements
    
    def _create_health_chart(self, health_data: dict):
        """Create health scores bar chart"""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        categories = ['Overall\nHealth', 'Vegetation\nHealth', 'Soil\nHealth', 
                     'Weather\nFavorability']
        scores = [
            health_data['overall_health'],
            health_data['vegetation_health'],
            health_data['soil_health'],
            health_data['weather_favorability']
        ]
        
        colors_list = ['#2E7D32', '#388E3C', '#795548', '#1976D2']
        
        bars = ax.bar(categories, scores, color=colors_list, alpha=0.8, edgecolor='black')
        ax.set_ylabel('Score (%)', fontsize=12, fontweight='bold')
        ax.set_title('Crop Health Metrics', fontsize=14, fontweight='bold')
        ax.set_ylim(0, 100)
        ax.axhline(y=80, color='green', linestyle='--', alpha=0.5, label='Excellent (80%)')
        ax.axhline(y=50, color='orange', linestyle='--', alpha=0.5, label='Fair (50%)')
        ax.grid(axis='y', alpha=0.3)
        ax.legend()
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}%', ha='center', va='bottom', fontweight='bold')
        
        return fig
    
    # DOCX Report Methods
    
    def _add_docx_title_page(self, doc: Document, data: dict):
        """Add title page to DOCX"""
        # Title
        title = doc.add_heading('AGRIVISION', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title.runs[0].font.color.rgb = RGBColor(46, 125, 50)
        
        subtitle = doc.add_heading('Agricultural Analysis Report', 2)
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        doc.add_paragraph()
        
        # Field info
        field_info = data['field_information']
        info = doc.add_paragraph()
        info.add_run(f"Field: ").bold = True
        info.add_run(f"{field_info['name']}\n")
        info.add_run(f"Crop Type: ").bold = True
        info.add_run(f"{field_info['crop_type'].title()}\n")
        info.add_run(f"Growth Stage: ").bold = True
        info.add_run(f"{field_info['growth_stage'].replace('_', ' ').title()}\n")
        info.add_run(f"Area: ").bold = True
        info.add_run(f"{field_info.get('area_hectares', 0):.2f} hectares\n")
        info.add_run(f"Report Date: ").bold = True
        info.add_run(f"{data['analysis_date']}")
        info.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Health score
        doc.add_paragraph()
        health = data['health_assessment']
        health_para = doc.add_paragraph()
        run = health_para.add_run(f"\nOverall Health Score: {health['overall_health']:.1f}%\n")
        run.font.size = Pt(20)
        run.font.bold = True
        run.font.color.rgb = RGBColor(46, 125, 50)
        health_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        category = doc.add_paragraph(health['health_category'])
        category.runs[0].font.size = Pt(14)
        category.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    def _add_docx_executive_summary(self, doc: Document, data: dict):
        """Add executive summary to DOCX"""
        doc.add_heading('Executive Summary', 1)
        
        health = data['health_assessment']
        yield_pred = data['yield_prediction']
        field_info = data['field_information']
        
        para = doc.add_paragraph()
        para.add_run(
            f"This report presents a comprehensive analysis of {field_info['name']}, "
            f"a {field_info.get('area_hectares', 0):.2f}-hectare field cultivating "
            f"{field_info['crop_type'].title()} currently in the "
            f"{field_info['growth_stage'].replace('_', ' ')} stage."
        )
        
        doc.add_paragraph()
        doc.add_heading('Key Findings:', 2)
        
        findings = [
            f"Overall crop health is assessed as {health['health_category']} with a score of {health['overall_health']:.1f}%",
            f"Predicted yield: {yield_pred['predicted_yield_tonnes_per_ha']:.2f} tonnes/ha ({yield_pred['yield_category']})",
            f"Vegetation health: {health['vegetation_health']:.1f}%",
            f"Water stress index: {health['water_stress_index']:.1f}%",
            f"Soil health: {health['soil_health']:.1f}%"
        ]
        
        for finding in findings:
            doc.add_paragraph(finding, style='List Bullet')
    
    def _add_docx_field_info(self, doc: Document, data: dict):
        """Add field information to DOCX"""
        doc.add_heading('Field Information', 1)
        
        field_info = data['field_information']
        
        table = doc.add_table(rows=6, cols=2)
        table.style = 'Light Grid Accent 1'
        
        headers = table.rows[0].cells
        headers[0].text = 'Property'
        headers[1].text = 'Value'
        
        rows_data = [
            ('Field Name', field_info['name']),
            ('Crop Type', field_info['crop_type'].title()),
            ('Growth Stage', field_info['growth_stage'].replace('_', ' ').title()),
            ('Area', f"{field_info.get('area_hectares', 0):.2f} hectares"),
            ('Analysis Date', data['analysis_date'])
        ]
        
        for i, (prop, val) in enumerate(rows_data, 1):
            cells = table.rows[i].cells
            cells[0].text = prop
            cells[1].text = val
    
    def _add_docx_health_section(self, doc: Document, data: dict):
        """Add health section to DOCX"""
        doc.add_heading('Crop Health Assessment', 1)
        
        health = data['health_assessment']
        
        table = doc.add_table(rows=6, cols=3)
        table.style = 'Light Grid Accent 1'
        
        headers = table.rows[0].cells
        headers[0].text = 'Metric'
        headers[1].text = 'Score (%)'
        headers[2].text = 'Category'
        
        metrics = [
            ('Overall Health', health['overall_health'], health['health_category']),
            ('Vegetation Health', health['vegetation_health'], 
             self._categorize_score(health['vegetation_health'])),
            ('Water Stress Index', health['water_stress_index'],
             self._categorize_score(100 - health['water_stress_index'])),
            ('Soil Health', health['soil_health'],
             self._categorize_score(health['soil_health'])),
            ('Weather Favorability', health['weather_favorability'],
             self._categorize_score(health['weather_favorability']))
        ]
        
        for i, (metric, score, category) in enumerate(metrics, 1):
            cells = table.rows[i].cells
            cells[0].text = metric
            cells[1].text = f"{score:.1f}"
            cells[2].text = category
    
    def _add_docx_yield_section(self, doc: Document, data: dict):
        """Add yield section to DOCX"""
        doc.add_heading('Yield Prediction & Optimization', 1)
        
        yield_data = data['yield_prediction']
        
        para = doc.add_paragraph()
        para.add_run('Predicted Yield: ').bold = True
        para.add_run(f"{yield_data['predicted_yield_tonnes_per_ha']:.2f} tonnes/ha\n")
        para.add_run('Confidence Level: ').bold = True
        para.add_run(f"{yield_data['confidence_percentage']}%\n")
        para.add_run('Yield Category: ').bold = True
        para.add_run(f"{yield_data['yield_category']}")
    
    def _add_docx_indices_section(self, doc: Document, data: dict):
        """Add indices section to DOCX"""
        doc.add_heading('Vegetation Indices', 1)
        
        indices = data['vegetation_indices']
        main_indices = ['NDVI', 'EVI', 'SAVI', 'NDWI', 'NDMI', 'GNDVI']
        
        table = doc.add_table(rows=len(main_indices)+1, cols=3)
        table.style = 'Light Grid Accent 1'
        
        headers = table.rows[0].cells
        headers[0].text = 'Index'
        headers[1].text = 'Value'
        headers[2].text = 'Interpretation'
        
        for i, idx in enumerate(main_indices, 1):
            if idx in indices:
                cells = table.rows[i].cells
                cells[0].text = idx
                cells[1].text = f"{indices[idx]:.3f}"
                cells[2].text = self._interpret_index(idx, indices[idx])
    
    def _add_docx_environmental_section(self, doc: Document, data: dict):
        """Add environmental section to DOCX"""
        doc.add_heading('Environmental Conditions', 1)
        
        doc.add_heading('Soil Properties', 2)
        soil = data['soil_analysis']
        
        for key, value in soil.items():
            para = doc.add_paragraph()
            para.add_run(f"{key.replace('_', ' ').title()}: ").bold = True
            para.add_run(f"{value:.2f}" if isinstance(value, (int, float)) else str(value))
        
        doc.add_heading('Weather Conditions', 2)
        weather = data['weather_data']
        
        for key, value in weather.items():
            para = doc.add_paragraph()
            para.add_run(f"{key.replace('_', ' ').title()}: ").bold = True
            para.add_run(f"{value:.2f}" if isinstance(value, (int, float)) else str(value))
    
    def _add_docx_recommendations(self, doc: Document, data: dict):
        """Add recommendations to DOCX"""
        doc.add_heading('Management Recommendations', 1)
        
        recommendations = data['health_assessment']['recommendations']
        
        for i, rec in enumerate(recommendations, 1):
            doc.add_heading(f"{i}. {rec['category']} [{rec['priority']} Priority]", 2)
            
            para = doc.add_paragraph()
            para.add_run('Issue: ').bold = True
            para.add_run(f"{rec['issue']}\n")
            para.add_run('Recommended Action: ').bold = True
            para.add_run(f"{rec['action']}\n")
            para.add_run('Expected Impact: ').bold = True
            para.add_run(rec['expected_improvement'])
    
    # Helper methods
    
    def _get_health_color(self, score: float) -> str:
        """Get color based on health score"""
        if score >= 80:
            return '#2E7D32'
        elif score >= 65:
            return '#689F38'
        elif score >= 50:
            return '#FBC02D'
        elif score >= 35:
            return '#F57C00'
        else:
            return '#D32F2F'
    
    def _categorize_score(self, score: float) -> str:
        """Categorize a score"""
        if score >= 80:
            return "Excellent"
        elif score >= 65:
            return "Good"
        elif score >= 50:
            return "Fair"
        elif score >= 35:
            return "Poor"
        else:
            return "Critical"
    
    def _interpret_index(self, index: str, value: float) -> str:
        """Interpret vegetation index value"""
        interpretations = {
            'NDVI': {
                (0.8, 1.0): 'Very healthy vegetation',
                (0.6, 0.8): 'Healthy vegetation',
                (0.4, 0.6): 'Moderate vegetation',
                (0.2, 0.4): 'Sparse vegetation',
                (0.0, 0.2): 'Bare soil/stressed'
            },
            'EVI': {
                (0.6, 1.0): 'Very high vigor',
                (0.4, 0.6): 'High vigor',
                (0.2, 0.4): 'Moderate vigor',
                (0.0, 0.2): 'Low vigor'
            },
            'NDWI': {
                (0.2, 1.0): 'High water content',
                (0.0, 0.2): 'Moderate water content',
                (-0.3, 0.0): 'Low water content',
                (-1.0, -0.3): 'Very low water'
            },
            'NDMI': {
                (0.4, 1.0): 'High moisture',
                (0.2, 0.4): 'Moderate moisture',
                (0.0, 0.2): 'Low moisture',
                (-1.0, 0.0): 'Very low moisture'
            }
        }
        
        if index not in interpretations:
            return 'See reference'
        
        for (min_val, max_val), interp in interpretations[index].items():
            if min_val <= value < max_val:
                return interp
        
        return 'Out of normal range'
    
    def _soil_ph_status(self, ph: float) -> str:
        """Interpret soil pH"""
        if 6.0 <= ph <= 7.5:
            return 'Optimal'
        elif 5.5 <= ph < 6.0 or 7.5 < ph <= 8.0:
            return 'Acceptable'
        else:
            return 'Needs adjustment'
    
    def _nutrient_status(self, value: float, nutrient: str) -> str:
        """Interpret nutrient levels"""
        thresholds = {
            'N': [(60, float('inf'), 'High'), (30, 60, 'Adequate'), (0, 30, 'Low')],
            'P': [(30, float('inf'), 'High'), (15, 30, 'Adequate'), (0, 15, 'Low')],
            'K': [(200, float('inf'), 'High'), (100, 200, 'Adequate'), (0, 100, 'Low')]
        }
        
        for min_val, max_val, status in thresholds.get(nutrient, []):
            if min_val <= value < max_val:
                return status
        
        return 'Unknown'
    
    def _om_status(self, om: float) -> str:
        """Interpret organic matter"""
        if om >= 3.0:
            return 'High'
        elif om >= 2.0:
            return 'Adequate'
        else:
            return 'Low'