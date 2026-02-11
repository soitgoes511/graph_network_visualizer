import io
import re
from pypdf import PdfReader
from docx import Document

def extract_links(text):
    # Basic regex for URLs
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(url_pattern, text)

def parse_pdf(file_content: bytes, logger=None):
    if logger: logger("Parsing PDF document...")
    text = ""
    links = []
    try:
        reader = PdfReader(io.BytesIO(file_content))
        total_pages = len(reader.pages)
        if logger: logger(f"PDF has {total_pages} pages")
        
        for i, page in enumerate(reader.pages):
            if logger and i % 5 == 0: logger(f"Processing page {i+1}/{total_pages}")
            text += page.extract_text() + "\n"
            # Extract annotations (links) if available
            if "/Annots" in page:
                for annot in page["/Annots"]:
                    obj = annot.get_object()
                    if "/A" in obj and "/URI" in obj["/A"]:
                        links.append(obj["/A"]["/URI"])
    except Exception as e:
        if logger: logger(f"Error parsing PDF: {e}")
        print(f"Error parsing PDF: {e}")
    
    # Also find links in text
    text_links = extract_links(text)
    links.extend(text_links)
    
    if logger: logger(f"PDF parsing complete. Found {len(links)} links.")
    return {"text": text, "links": list(set(links))}

def parse_docx(file_content: bytes, logger=None):
    if logger: logger("Parsing DOCX document...")
    text = ""
    links = []
    try:
        doc = Document(io.BytesIO(file_content))
        if logger: logger(f"DOCX has {len(doc.paragraphs)} paragraphs")
        
        for para in doc.paragraphs:
            text += para.text + "\n"
            
        # Extract hyperlinks from relationships
        # Note: This iterates over all relationships in the document part, 
        # which includes all hyperlinks in the body.
        for rel in doc.part.rels.values():
            if "hyperlink" in rel.reltype:
                 links.append(rel.target_ref)
        
        # Extract links from text just in case
        text_links = extract_links(text)
        links.extend(text_links)

    except Exception as e:
        if logger: logger(f"Error parsing DOCX: {e}")
        print(f"Error parsing DOCX: {e}")

    if logger: logger(f"DOCX parsing complete. Found {len(links)} links.")
    return {"text": text, "links": list(set(links))}
