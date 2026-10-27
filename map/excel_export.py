"""Small, dependency-free OOXML writer for the application's tabular export.

Untrusted strings are explicitly inline strings, never spreadsheet formulas.
"""
from datetime import datetime,date,timezone
from io import BytesIO
import math,re,zipfile
from zoneinfo import ZoneInfo
from xml.etree.ElementTree import Element,SubElement,tostring

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
def column_name(index):
    name=''
    while index:index,part=divmod(index-1,26);name=chr(65+part)+name
    return name
def xml_text(value):return re.sub('[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]','',str(value)).encode('utf-8','replace').decode('utf-8')[:32767]
def workbook_bytes(grid):
    if not grid or not grid[0]:raise ValueError('Die Tabelle benötigt Spaltenüberschriften.')
    if len(grid)>1048576 or max(map(len,grid))>16384:raise ValueError('Die Tabelle überschreitet die Excel-Grenzen.')
    root=Element('worksheet',xmlns=NS)
    views=SubElement(root,'sheetViews');view=SubElement(views,'sheetView',workbookViewId='0')
    SubElement(view,'pane',ySplit='1',topLeftCell='A2',activePane='bottomLeft',state='frozen')
    cols=SubElement(root,'cols')
    for i in range(len(grid[0])):SubElement(cols,'col',min=str(i+1),max=str(i+1),width='12' if i==0 else '28',customWidth='1')
    data=SubElement(root,'sheetData')
    for r,values in enumerate(grid,1):
        row=SubElement(data,'row',r=str(r))
        for c,value in enumerate(values,1):
            cell=SubElement(row,'c',r=column_name(c)+str(r),s='1' if r==1 else '0')
            if value is None:continue
            if isinstance(value,(datetime,date)):
                if isinstance(value,datetime):
                    if value.tzinfo:value=value.astimezone(ZoneInfo("Europe/Berlin")).replace(tzinfo=None)
                else:value=datetime.combine(value,datetime.min.time())
                cell.set('s','2');SubElement(cell,'v').text=str((value-datetime(1899,12,30)).total_seconds()/86400)
            elif ((isinstance(value,int) and not isinstance(value,bool) and abs(value)<10**15) or (isinstance(value,float) and math.isfinite(value) and abs(value)<10**15)):
                SubElement(cell,'v').text=str(value)
            else:
                cell.set('t','inlineStr');text=SubElement(SubElement(cell,'is'),'t',{'{http://www.w3.org/XML/1998/namespace}space':'preserve'});text.text=xml_text(value)
    SubElement(root,'autoFilter',ref='A1:'+column_name(len(grid[0]))+str(len(grid)))
    files={
      '[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
      '_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
      'xl/workbook.xml':'<workbook xmlns="'+NS+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Anmeldungen" sheetId="1" r:id="rId1"/></sheets></workbook>',
      'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
      'xl/styles.xml':'<styleSheet xmlns="'+NS+'"><numFmts count="1"><numFmt numFmtId="164" formatCode="dd.mm.yyyy hh:mm"/></numFmts><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF174D68"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
      'xl/worksheets/sheet1.xml':tostring(root,encoding='utf-8',xml_declaration=True),
    }
    buffer=BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,content in files.items():archive.writestr(name,content)
    return buffer.getvalue()
