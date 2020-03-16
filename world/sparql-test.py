import requests


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

print(str(getPopulationData()))