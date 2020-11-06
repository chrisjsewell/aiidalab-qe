"""Widgets for the monitoring of processes."""
import os
from collections import deque
from dataclasses import dataclass

import traitlets
import ipywidgets as ipw
from aiida.cmdline.utils.query.calculation import CalculationQueryBuilder
from aiida.orm import load_node
from aiida.orm import ProcessNode
from aiida.orm.utils import load_node
from widgets import ProcessOutputFollower



def get_calc_job_output(process):
    from aiidalab_widgets_base.process import get_running_calcs
    previous_calc_id = None
    num_lines = 0

    while not process.is_sealed:
        calc = None
        for calc in get_running_calcs(process):
            if calc.id == previous_calc_id:
                break
        else:
            if calc:
                previous_calc_id = calc.id

        if calc and 'remote_folder' in calc.outputs:
            f_path = os.path.join(calc.outputs.remote_folder.get_remote_path(),
                                  calc.attributes['output_filename'])
            if os.path.exists(f_path):
                with open(f_path) as fobj:
                    new_lines = fobj.readlines()[num_lines:]
                    num_lines += len(new_lines)
                    yield from new_lines


class ProgressBarWidget(ipw.VBox):
    """A bar showing the proggress of a process."""

    process = traitlets.Instance(ProcessNode, allow_none=True)

    def __init__(self, **kwargs):
        self.correspondance = {
            None: (0, 'warning'),
            "created": (0, 'info'),
            "running": (1, 'info'),
            "waiting": (1, 'info'),
            "killed": (2, 'danger'),
            "excepted": (2, 'danger'),
            "finished": (2, 'success'),
        }
        self.bar = ipw.IntProgress(  # pylint: disable=blacklisted-name
            value=0,
            min=0,
            max=2,
            step=1,
            bar_style='warning',  # 'success', 'info', 'warning', 'danger' or ''
            orientation='horizontal',
            layout=ipw.Layout(width="auto")
        )
        self.state = ipw.HTML(
            description="Calculation state:", value='',
            style={'description_width': '100px'},
        )
        super().__init__(children=[self.state, self.bar], **kwargs)

    @traitlets.observe('process')
    def update(self, _=None):
        """Update the bar."""
        self.bar.value, self.bar.bar_style = self.correspondance[self.current_state]
        if self.current_state is None:
            self.state.value = 'N/A'
        else:
            self.state.value = self.current_state.capitalize()

    @property
    def current_state(self):
        if self.process is not None:
            return self.process.process_state.value


class LogOutputWidget(ipw.VBox):

    def __init__(self, title='Output:', num_lines_shown=3, **kwargs):
        self.description = ipw.Label(value=title)
        self.last_lines = ipw.HTML()

        self.lines = []
        self.lines_shown = deque([''] * num_lines_shown, maxlen=num_lines_shown)

        self.raw_log = ipw.Textarea(
            layout=ipw.Layout(
                width='auto',
                height='auto',
                display='flex',
                flex='1 1 auto',
            ),
            disabled=True)

        self.accordion = ipw.Accordion(children=[self.raw_log])
        self.accordion.set_title(0, 'Raw log')
        self.accordion.selected_index = None

        self._update()
        super().__init__(children=[self.description, self.last_lines, self.accordion], **kwargs)

    def clear(self):
        self.lines.clear()
        self.lines_shown.clear()
        self._update()

    def append_line(self, line):
        self.lines.append(line.strip())
        self.lines_shown.append("{:03d}: {}".format(len(self.lines), line.strip()))
        self._update()

    @staticmethod
    def _format_code(text):
        return '<pre style="background-color: #1f1f2e; color: white;">{}</pre>'.format(text)

    def _update(self):
        with self.hold_trait_notifications():
            lines_to_show = self.lines_shown.copy()
            while len(lines_to_show) < self.lines_shown.maxlen:
                lines_to_show.append(' ')

            self.last_lines.value = self._format_code('\n'.join(lines_to_show))
            self.raw_log.value = '\n'.join(self.lines)


class ProcessStatusWidget(ipw.VBox):

    process = traitlets.Instance(ProcessNode, allow_none=True)

    def __init__(self, **kwargs):
        self.progress_bar = ProgressBarWidget()
        self.log_output = ProcessOutputFollower(layout=ipw.Layout(min_height='150px', max_height='400px'))
        self.process_id_text = ipw.Text(
            value='',
            description='Process:',
            layout=ipw.Layout(width='auto', flex="1 1 auto"),
            disabled=True,
        )
        ipw.dlink((self, 'process'), (self.process_id_text, 'value'),
                  transform=lambda proc: str(proc))
        ipw.dlink((self, 'process'), (self.log_output, 'process'))
        ipw.dlink((self, 'process'), (self.progress_bar, 'process'))

        super().__init__(children=[
            self.progress_bar,
            self.process_id_text,
            self.log_output,
            ], **kwargs)

    def update(self):
        self.progress_bar.update()


class ProcessSelector(ipw.HBox):
    _NO_PROCESS = object()

    value = traitlets.Int(allow_none=True)

    FMT_WORKCHAIN = "{wc.pk:6}{wc.ctime:>10}\t{wc.state:<16}\t{wc.formula}"

    def __init__(self, **kwargs):
        self.work_chains_selector = ipw.Dropdown(
            description="Process",
            options=[('New calculation...', self._NO_PROCESS)],
            layout=ipw.Layout(width='auto', flex="1 1 auto"),
        )
        ipw.dlink((self.work_chains_selector, 'value'), (self, 'value'),
                  transform=lambda pk: None if pk is self._NO_PROCESS else pk)

        self.refresh_work_chains_button = ipw.Button(
            description='Refresh')
        self.refresh_work_chains_button.on_click(self.refresh_work_chains)
        self.refresh_work_chains()
        super().__init__(children=[self.work_chains_selector, self.refresh_work_chains_button], **kwargs)

    @dataclass
    class WorkChainData:
        pk: int
        ctime: str
        state: str
        formula: str

    @classmethod
    def find_work_chains(cls):
        builder = CalculationQueryBuilder()
        filters = builder.get_filters(
            process_label = 'PwBandsWorkChain',
        )
        query_set = builder.get_query_set(
            filters=filters,
            order_by={'ctime': 'desc'},
        )
        projected = builder.get_projected(
            query_set, projections=['pk', 'ctime', 'state'])

        header = projected[0]
        for process in projected[1:]:
            pk = process[0]
            try:
                formula = load_node(pk).inputs.structure.get_formula()
            except:
                raise
                formula = ''
            yield cls.WorkChainData(formula=formula, *process)

    def refresh_work_chains(self, _=None):
        # This function may trigger the value to be reset, see issue:
        # https://github.com/jupyter-widgets/ipywidgets/issues/2230
        self.work_chains_selector.options = \
            [("New calculation...", self._NO_PROCESS)] + \
            [(self.FMT_WORKCHAIN.format(wc=wc), wc.pk) for wc in self.find_work_chains()]

    @traitlets.observe('value')
    def _observe_value(self, change):
        if change['old'] == change['new']:
            return

        new = self._NO_PROCESS if change['new'] is None else change['new']

        if new not in {pk for _, pk in self.work_chains_selector.options}:
            self.refresh_work_chains()

        self.work_chains_selector.value = new
