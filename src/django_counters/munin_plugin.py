import re
from pycounters import reporters
import pycounters.utils.munin

class DjangoCountersMuninPlugin(pycounters.utils.munin.Plugin):

    def __init__(self,json_output_file=None,category=None):
        super(DjangoCountersMuninPlugin,self).__init__(json_output_file=json_output_file)
        self.category=category


    def auto_generate_config_from_json(self):
        values = reporters.JSONFileReporter.safe_read(self.output_file)

        counters = filter(lambda x : not re.match("^__.*__$",x) , values.keys())
        counters = sorted(counters)

        # now they counters are sorted, you can start by checking prefixes

        title_prefix = self.category + ": " if self.category else ""

        config = []

        active_view=None
        active_config = None
        for counter in counters:
            if not counter.startswith("v_"):
                continue # not generated by count_view

            view_name, counter_name = counter.split(".", 1)
            view_name = view_name[2:] # remove v_

            if active_view is None or active_view != view_name:
                ## new counter found
                active_view = view_name
                active_config = {}
                config.append(active_config)
                active_config["id"]=self.category + "_" + counter if self.category else counter
                active_config["global"]=dict(category=self.category,
                                            title="%sAverage times for view %s " % (title_prefix, counter),
                                            vlabel="time")

            if counter_name == "_rps":
                # request per second, another chart
                rps_config = {}
                config.append(rps_config)
                rps_config["id"]=self.category + "_" + counter if self.category else counter
                rps_config["global"]=dict(category=self.category,
                                          title="%sRequests per second for view %s " % (title_prefix ,view_name),
                                          vlabel="rps")

                rps_config["data"]=[ dict(counter=counter,label="Requests per sec",draw="LINE1") ]

            elif counter_name == "_total":
                active_config["data"]=[dict(counter=counter,label="Total",draw="LINE1")]

            else:
                active_config["data"].append(
                    dict(counter=counter,label=counter_name,draw="AREASTACK")
                )

                
        return config

    def output_config(self,config):
        config = self.auto_generate_config_from_json()
        super(DjangoCountersMuninPlugin,self).output_config(config)


    def output_data(self,config):
        config = self.auto_generate_config_from_json()
        super(DjangoCountersMuninPlugin,self).output_data(config)
