import re
from pycounters import reporters
import pycounters.utils.munin
import string

class DjangoCountersMuninPlugin(pycounters.utils.munin.Plugin):

    def __init__(self,json_output_file=None,category=None):
        super(DjangoCountersMuninPlugin,self).__init__(json_output_file=json_output_file)
        self.category=category


    def auto_generate_config_from_json(self):
        values = reporters.JSONFileReporter.safe_read(self.output_file)

        counters = filter(lambda x : not re.match("^__.*__$",x) , values.keys())
        counters = sorted(counters)

        # now they counters are sorted, you can start by checking prefixes

        config = []

        active_counter=None
        active_config = None
        for counter in counters:
            if active_counter is None or not counter.startswith(active_counter+"."):
                ## new counter found
                active_counter = counter
                active_config = {}
                config.append(active_config)
                active_config["id"]=self.category + "_" + counter if self.category else counter
                active_config["global"]=dict(category=self.category,
                                            title="%s: Average times for view %s " % (self.category,counter),
                                            vlabel="time")

                active_config["data"]=[ dict(counter=counter,label="Total",draw="LINE1") ]

                continue

            active_config["data"].append(
                dict(counter=counter,label=counter[len(active_counter)+1:],
                     draw="AREASTACK")
            )

                
        return config

    def output_config(self,config):
        config = self.auto_generate_config_from_json()
        super(DjangoCountersMuninPlugin,self).output_config(config)


    def output_data(self,config):
        config = self.auto_generate_config_from_json()
        super(DjangoCountersMuninPlugin,self).output_data(config)
