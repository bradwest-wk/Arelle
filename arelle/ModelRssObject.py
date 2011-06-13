'''
Created on Nov 11, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, re, xml.dom.minidom, xml.parsers.expat
from collections import defaultdict
from arelle import (XbrlConst, XbrlUtil, XmlUtil, UrlUtil, ModelXbrl, ModelDocument, ModelObject, ModelVersObject)
from arelle.ModelValue import qname
from email.utils import parseaddr

edgr = "http://www.sec.gov/Archives/edgar"
edgrDescription = "{http://www.sec.gov/Archives/edgar}description"
edgrFile = "{http://www.sec.gov/Archives/edgar}file"
edgrType = "{http://www.sec.gov/Archives/edgar}type"
edgrUrl = "{http://www.sec.gov/Archives/edgar}url"

class RssWatchOptions():
    def __init__(self):
        self.feedSource = ""
        self.feedSourceUri = None
        self.matchTextExpr = ""
        self.formulaFileUri = ""
        self.logFileUri = ""
        self.emailAddress = ""
        self.validateXbrlRules = False
        self.validateDisclosureSystemRules = False
        self.validateCalcLinkbase = False
        self.validateFormulaAssertions = False
        self.alertMatchedFactText = False
        self.alertAssertionUnsuccessful = False
        self.alertValiditionError = False
        
        # Note: if adding to this list keep DialogRssWatch in sync
class ModelRssObject(ModelDocument.ModelDocument):
    def __init__(self, modelXbrl, 
                 type=ModelDocument.Type.RSSFEED, 
                 uri=None, filepath=None, xmlDocument=None):
        super().__init__(modelXbrl, type, uri, filepath, xmlDocument)
        self.items = []
        
    def rssFeedDiscover(self, rootElement):
        # add self to namespaced document
        self.xmlRootElement = rootElement
        for itemElt in rootElement.getElementsByTagName("item"):
            self.items.append(ModelRssItem(self, itemElt))
            
class ModelRssItem(ModelObject.ModelObject):
    def __init__(self, modelDocument, element):
        super().__init__(modelDocument, element)
        if (self.modelXbrl.modelManager.rssWatchOptions.latestPubDate and 
            self.pubDate <= self.modelXbrl.modelManager.rssWatchOptions.latestPubDate):
            self.status = _("tested")
        else:
            self.status = _("not tested")
        self.results = []
        self.assertions = None
        
    @property
    def cikNumber(self):
        return XmlUtil.text(XmlUtil.descendant(self, edgr, "cikNumber"))
    
    @property
    def accessionNumber(self):
        return XmlUtil.text(XmlUtil.descendant(self, edgr, "accessionNumber"))
    
    @property
    def companyName(self):
        return XmlUtil.text(XmlUtil.descendant(self, edgr, "companyName"))
    
    @property
    def formType(self):
        return XmlUtil.text(XmlUtil.descendant(self, edgr, "formType"))
    
    @property
    def pubDate(self):
        try:
            return self._pubDate
        except AttributeError:
            from arelle.UrlUtil import parseRfcDatetime
            self._pubDate = parseRfcDatetime(XmlUtil.text(XmlUtil.descendant(self, None, "pubDate")))
            return self._pubDate
    @property
    def filingDate(self):
        try:
            return self._filingDate
        except AttributeError:
            import datetime
            self._filingDate = None
            date = XmlUtil.text(XmlUtil.descendant(self, edgr, "filingDate"))
            d = date.split("/") 
            if d and len(d) == 3:
                self._filingDate = datetime.date(int(d[2]),int(d[0]),int(d[1]))
            return self._filingDate
    
    @property
    def period(self):
        per = XmlUtil.text(XmlUtil.descendant(self, edgr, "period"))
        if per and len(per) == 8:
            return "{0}-{1}-{2}".format(per[0:4],per[4:6],per[6:8])
        return None
    
    @property
    def fiscalYearEnd(self):
        yrEnd = XmlUtil.text(XmlUtil.descendant(self, edgr, "fiscalYearEnd"))
        if yrEnd and len(yrEnd) == 4:
            return "{0}-{1}".format(yrEnd[0:2],yrEnd[2:4])
        return None
    
    @property
    def url(self):
        try:
            return self._url
        except AttributeError:
            self._url = None
            for instDocElt in XmlUtil.descendants(self, edgr, "xbrlFile"):
                if instDocElt.get(edgrType).endswith(".INS"):
                    self._url = instDocElt.get(edgrUrl)
                    break
            return self._url
        
    @property
    def zippedUrl(self):
        # modify url to use zip file
        path, sep, file = self.url.rpartition("/")
        return path + sep + self.accessionNumber + "-xbrl.zip" + sep + file
        
        
    @property
    def htmURLs(self):
        try:
            return self._htmURLs
        except AttributeError:
            self._htmURLs = [
                (instDocElt.get(edgrDescription),instDocElt.get(edgrUrl))
                  for instDocElt in XmlUtil.descendants(self, edgr, "xbrlFile")
                    if instDocElt.get(edgrFile).endswith(".htm")]
            return self._htmURLs
        
    def setResults(self, modelXbrl):
        self.results = []
        # put error codes first, sorted, then assertion result (dict's)
        for error in modelXbrl.errors:
            if isinstance(error,dict):  # assertion results
                self.assertions = error
            else:   # error code results
                self.results.append(error)
        self.results.sort()
        self.assertionUnsuccessful = False
        for error in self.results:
            if isinstance(error,dict):
                self.results.append(error)
                # check if any not successful
                for countSuccessful, countNotsuccessful in error.items():
                    if countNotsuccessful > 0:
                        self.assertionUnsuccessful = True
        if self.results:
            self.status = " \n".join(str(result) for result in self.results)
        else:
            self.status = "pass"
    
    @property
    def propertyView(self):
        return (("CIK", self.cikNumber),
                ("company", self.companyName),
                ("published", self.pubDate),
                ("form type", self.formType),
                ("filing date", self.filingDate),
                ("period", self.period),
                ("year end", self.fiscalYearEnd),
                ("status", self.status),
                ("instance", os.path.basename(self.url)),
                )
    def __repr__(self):
        return ("rssItem[{0}]{1})".format(self.objectId(),self.propertyView))

