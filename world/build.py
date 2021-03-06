# Created by Chang Chia-huan
import argparse, json, re, csv, urllib.request, io, datetime, math, requests

parser = argparse.ArgumentParser(description = "This script generates an svg map for the COVID-19 outbreak globally")
parser.add_argument("-c", "--count", help = "Generate case count map", action = "store_const", const = "count", dest = "type")
parser.add_argument("-p", "--pcapita", help = "(Not yet available) Generate per capita cases map", action = "store_const", const = "pcapita", dest = "type")
# Only count works for now
args = vars(parser.parse_args())

def get_value(count, pcapita):
    if args["type"] == "count":
        return count
    elif args["type"] == "pcapita":
        return pcapita

with open("data.json", newline = "", encoding = "utf-8") as file:
    main = json.loads(file.read())

# fetch figures from Wikipedia; credits: Dan Polansky
def grabFromTemplate():
    url="https://en.wikipedia.org/wiki/Template:2019%E2%80%9320_coronavirus_pandemic_data"
    allLines = []
    for line in urllib.request.urlopen(url):
      allLines.append((line.decode()).rstrip())
    allLines = " ".join(allLines)
    allLines = re.sub("^.*jquery-tablesorter", "", allLines)
    allLines = re.sub("</table.*", "", allLines)
    allLines = re.sub("<(th|td)[^>]*>", r"<td>", allLines)
    allLines = re.sub("</?(span|img|a|sup)[^>]*>", "", allLines)
    allLines = re.sub("</(th|td|tr)[^>]*>", "", allLines)
    allLines = re.sub("&#91.*?&#93", "", allLines)
    allLines = re.sub(",", "", allLines)
    allLines = re.sub("<small>.*?</small>;?", "", allLines)
    allLines = re.sub("</?i>", "", allLines)

    outData = {}
    rows = allLines.split("<tr> ")
    for row in rows:
        try:
            cols = row.split("<td>")
            cols.pop(0)
            cols.pop(0)
            place = cols.pop(0)
            cols = cols[0:3]
            cols = [int(col) for col in cols]
        except:
            continue
        outData[(place.rstrip()).replace(";", "")] = cols
    #for key, value in outData.items():
    #  print key, value
    return outData
template = grabFromTemplate()

def getPopulationData():
    url = 'https://query.wikidata.org/sparql'
    query = '''
        SELECT ?isocode ?population WHERE {
        ?country wdt:P1082 ?population.
        ?country wdt:P297 ?isocode
        }
    '''
    response = requests.get(url, params = {'format': 'json', 'query': query})
    return { p['isocode']['value'] : int(p['population']['value']) for p in response.json()['results']['bindings'] }

population_data = getPopulationData()
## Population data
for place, data in main.items():
    code = place[1:].upper()
    population = population_data.get(code, None)
    data['population'] = population

for place in main:
    if main[place]["updated"] == None:
        for place2 in template:
            place2 = place2.replace(";", "")
            if place2.find(main[place]["names"]["JHU"]) > -1:
                main[place]["names"]["wikipedia"] = place2
                main[place]["cases"] = template[place2][0]
                main[place]["recovered"] = template[place2][2]
                main[place]["updated"] = "from Wikipedia"
                break

with urllib.request.urlopen("https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Confirmed.csv") as response:
    reader = csv.reader(io.TextIOWrapper(response, encoding = "utf-8"), delimiter = ",")
    for row in reader:
        if row[1] in ["Country/Region", "Cruise Ship"]:
            if row[1] == "Country/Region":
                global date
                date = row[-1]
            continue
        row[1] = row[1].replace("*", "")
        for place in main:
            if main[place]["updated"] != None:
                continue
            else:
                if main[place]["names"]["JHU"] == row[0]:
                    main[place]["cases"] = int(row[-1])
                    main[place]["updated"] = "from JHU"
                    break
                elif main[place]["names"]["JHU"] == row[1]:
                    main[place]["cases"] += int(row[-1])
                    main[place]["updated"] = "from JHU"
                    break

## Calculate population cases per capita:
for place, data in main.items():
    try: 
        data['pcapita'] = 1000000 * data['cases'] / data['population']
    except:
        data['pcapita'] = None

thresholds = [0, 1, 10, 100, 1000, 10000]
thresholds_pc = [0, 0.01, 0.1, 1, 10, 100, 1000]
colours = ["#e0e0e0", "#ffC0C0","#ee7070","#c80200","#900000","#510000", "#aa00ff"]

## Calculate thresholds
for place, data in main.items():
    for idx, value in enumerate(thresholds):
        try:
            if data['cases'] > value:
                data['threshold_ca'] = value
                data['color_ca'] = colours[idx]
        except:
            data['cthreshold'] = 0
            data['color_ca'] = colours[0]
    for idx, value in enumerate(thresholds_pc):
        try:
            if data['pcapita'] > value:
                data['threshold_pc'] = value
                data['color_pc'] = colours[idx]
        except:
            data['threshold_pc'] = 0
            data['color_pc'] = colours[0]

## Calculate color maps
color_map_ca = { 
    color : [place for place, data in main.items() if data.get('color_ca', colours[0]) == color] 
    for color in colours
}

color_map_pc = { 
    color : [place for place, data in main.items() if data.get('color_pc', colours[0]) == color] 
    for color in colours
}


with open("template.svg", "r", newline = "", encoding = "utf-8") as file_in:
    with open(get_value("counts.svg", "per-capita.svg"), "w", newline = "", encoding = "utf-8") as file_out:
        for r, row in enumerate(file_in):
            if r == 158:
                color_map = get_value(color_map_ca, color_map_pc)
                for color, places in color_map.items():
                    file_out.write(f"{', '.join(places)}\n{{\n   fill:{color};\n}}\n")
            else:
                file_out.write(row)

with open("data-generated.json", "w", newline = "", encoding = "utf-8") as file:
    file.write(json.dumps(main, indent = 2, ensure_ascii = False))

for place, attrs in main.items():
    print(place, attrs)

cases = []
for attrs in main.values():
    cases.append(attrs["cases"])
print("Total cases:", "{:,}".format(sum(cases)), "in", len(cases), "areas as of", date, "(JHU)")
print("Colours:", colours)
print("Thresholds:", thresholds, "Max:", max(cases))
