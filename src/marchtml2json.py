import bs4
import re
import requests
import json
import sys

_RE_DATAFIELD = re.compile("^(?P<tag>\d+)\s+-\s+(?P<name>.*)\s+\((?P<repeatable>NR|R)\)$", re.U + re.S)
_RE_INDICATOR_VALUE = re.compile("^(?P<key>.*)\s+-\s+(?P<value>.*)$", re.U + re.S)
_RE_CODE_VALUE = re.compile("^\$(?P<code>.)(-(?P<code2>.))?)\s+-\s+(?P<value>.*?)(\s+\((?P<repeatable>NR|R)\)?)?$", re.U + re.S)
_RE_SPACES = re.compile("\s+", re.U + re.S)

def get_marc(html):
    return MARCHTML2Json(html).get_dict()

def get_whole_json():
    session = requests.Session()
    ret = {}
    for tag in range(10, 900):
        print >> sys.stderr, "Retrieving tag %03d" % tag,
        r = session.get("http://www.loc.gov/marc/bibliographic/bd%03d.html" % tag)
        if r.status_code == 200:
            ret["%03d" % tag] = get_marc(r.text)
            print >> sys.stderr, "OK"
        else:
            print >> sys.stderr, 404

    return json.dumps(ret, sort_keys=True, indent=4, separators=(',', ': '))


class MARCHTML2Json(object):
    def __init__(self, html):
        self.soup = bs4.BeautifulSoup(html)

    def get_dict(self):
        ret = {}
        datafield_info = self.get_datafield_info()
        ret['name'] = datafield_info['name']
        ret['repeatable'] = datafield_info['repeatable'] == 'R'
        ret['indicators'] = self.get_indicators_info()
        ret['subfields'] = self.get_subfield_codes()
        ret['definition'] = self.get_field_definition()
        return ret

    def get_datafield_info(self):
        text = self.soup.h1.text.strip()
        return _RE_DATAFIELD.match(text).groupdict()

    def get_indicators_info(self):
        indicators = self.soup.table.findAll("td")
        assert(len(indicators) == 2)
        ret = []
        for indicator in indicators:
            ind = {'name':  indicator.em.string, 'values': {}}
            elems = [elem.strip() for elem in indicator.contents if type(elem) is bs4.element.NavigableString and elem.strip()]
            if not elems:
                elems = [_RE_SPACES.sub(' ', elem.get_text()).strip() for elem in indicator.find_all("li") if _RE_SPACES.sub(' ', elem.get_text()).strip()]
            if not elems:
                elems = [_RE_SPACES.sub(' ', elem.get_text()).strip() for elem in indicator.find_all("span") if _RE_SPACES.sub(' ', elem.get_text()).strip()]
            for elem in elems:
                g = _RE_INDICATOR_VALUE.match(elem).groupdict()
                ind['values'][g['key'.strip()]] = g['value'].strip()
            ret.append(ind)
        return {"1": ret[0], "2": ret[1]}

    def get_subfield_codes(self):
        subfields = self.soup.find_all("table")[1].find_all("tr")[2]
        ret = {}
        last_subfield = None
        for td in subfields.find_all("td"):
            elems = [elem.strip() for elem in td.contents if type(elem) is bs4.element.NavigableString and elem.strip()]
            if not elems:
                elems = [_RE_SPACES.sub(' ', elem.get_text()).strip() for elem in td.find_all("li") if _RE_SPACES.sub(' ', elem.get_text()).strip()]
            for elem in elems:
                elem = elem.strip()
                g = _RE_CODE_VALUE.match(elem)
                if g:
                    g = g.groupdict()
                    last_subfield = {'name': g['value'],
                                        'static': False,
                                        'repeatable': g.get('repeatable', 'R') == 'R'}
                    if g.get('code2'):
                        for code in range(ord(g['code']), ord(g['code2']) + 1):
                            ret[chr(code)] = last_subfield
                    else:
                        ret[g['code']] = last_subfield
                else:
                    g = _RE_INDICATOR_VALUE.match(elem).groupdict()
                    if not last_subfield['static']:
                        last_subfield['static'] = True
                        last_subfield['staticValues'] = {}
                    last_subfield['staticValues'][g['key']] = {
                        "name": g['value'],
                        "value": g['key']}
        return ret

    def get_field_definition(self):
        definition = self.soup.find(class_="definition")
        if definition:
            return ' '.join(_RE_SPACES.sub(' ', row) for row in definition.stripped_strings if _RE_SPACES.sub(' ', row))
        return self.soup.h3.findNextSiblings("p")[0].text

if __name__ == "__main__":
    print get_whole_json()
