# standard library imports
import datetime as dt

# 3rd party library imports
from IPython.display import display
import ipywidgets as widgets
import xarray as xr

# local imports
from xco2qc import core

HTML_COLUMN_WIDTH = '30%'
CONTROL_COLUMN_WIDTH = '70%'
COMMON_BORDER = 'solid 1px'


class MetadataGUI(core.MapCO2core):
    """
    Create the GUI controls used by the jupyter notebook to add metadata.

    Attributes
    ----------
    gui_rows : list
        Each list item is a widget that controls some aspect of the metadata.
    gui : ipywidgets.VBox
        The metadata GUI
    num_pis : int
        Number of PIs involved with the deployment.
    qcer : dict
        contains editable text widgets for the name, organization,
        address, phone, and email of the person running the QC process
    vessel_id_text : Text widget
        Will contain the name of the ship.
    historical_ncfile : path or None
        If there is a historical netCDF file, we will try to use that to
        populate some metadata fields.
    """

    def __init__(self, num_pis=1, netcdf_dir=None):
        super().__init__(src_dir=netcdf_dir)

        self.num_pis = num_pis
        # Setup the path to the historical netCDF file if it exists.
        self.historical_ncfile = None
        if netcdf_dir is not None:
            historical_ncfile = netcdf_dir / core.HISTORICAL_NCFILE
            if historical_ncfile.exists():
                # if historical_ncfile.exists():
                self.historical_ncfile = historical_ncfile

    def run(self):

        self.gui_rows = []

        self.qcer = {}

        self.setup_pi_list_controls()
        self.setup_qcer_controls()
        self.setup_vessel_id_controls()
        self.setup_stationary_mobile_controls()

        self.setup_metadata_text_controls()

        # Setup all the rows of the GUI, arranged as a single column.
        self.gui = widgets.VBox(self.gui_rows)

        display(self.gui)

    def setup_metadata_text_controls(self):
        """
        Setup metadata widget controls.  We'll have a title and a description/
        instruction column on the left and the input box on the right.
        """

        self.acdd_attr_text_controls = {}
        properties = {
            'creator_name': {
                'type': 'acdd',
                'height': '80px',
                'description': (
                    "The name of the person (or other creator type specified "
                    "by the creator_type attribute) principally responsible "
                    "for creating this data."
                )
            },
            'creator_type': {
                'type': 'acdd',
                'height': '80px',
                'description': (
                    "Specifies type of creator with one of the following: "
                    "'person', 'group', 'institution', or 'position'. If this "
                    "attribute is not specified, the creator is assumed to be "
                    "a person."
                )
            },
            'creator_email': {
                'type': 'acdd',
                'height': '80px',
                'description': (
                    "The email address of the person (or other creator type "
                    "specified by the creator_type attribute) principally "
                    "responsible for creating this data."
                )
            },
            'creator_url': {
                'type': 'acdd',
                'height': '80px',
                'description': (
                    "The URL of the person (or other creator type "
                    "specified by the creator_type attribute) principally "
                    "responsible for creating this data."
                )
            },
            'history': {
                'type': 'acdd',
                'height': '80px',
                'description': (
                    "Provides an audit trail for modifications to the "
                    "original data."
                )
            },
            'infoUrl': {
                'type': 'erdap',
                'height': '80px',
                'description': (
                    "The URL of a web page with more information about "
                    "this dataset."
                )
            },
            'institution': {
                'type': 'acdd',
                'height': '80px',
                'description': (
                    "The name of the institution principally responsible "
                    "for originating this data."
                )
            },
            'keywords': {
                'type': 'acdd',
                'height': '160px',
                'description': (
                    "A comma-separated list of key words and/or phrases. "
                    "Keywords may be common words or phrases, terms from a "
                    "controlled vocabulary (GCMD is often used), or URIs for "
                    "terms from a controlled vocabulary (see also "
                    "\"keywords_vocabulary\" attribute)."
                )
            },
            'license': {
                'type': 'acdd',
                'height': '160px',
                'description': (
                    "Provide the URL to a standard or specific license, "
                    "enter \"Freely Distributed\" or \"None\", or describe "
                    "any restrictions to data access and distribution in "
                    "free text."
                )
            },
            'references': {
                'type': 'acdd',
                'height': '160px',
                'description': (
                    "Published or web-based references that describe "
                    "the data or methods used to produce it. Recommend "
                    "URIs (such as a URL or DOI) for papers or other "
                    "references."
                )
            },
            'standard_name_vocabulary': {
                'type': 'acdd',
                'height': '80px',
                'description': (
                    "The name and version of the controlled vocabulary "
                    "from which variable standard names are taken. (Values "
                    "for any standard_name attribute must come from the "
                    "CF Standard Names vocabulary for the data file or "
                    "product to comply with CF.) Example: 'CF Standard "
                    "Name Table v27'."
                )
            },
            'summary': {
                'type': 'acdd',
                'height': '160px',
                'description': (
                    "A paragraph describing the dataset, analogous to an "
                    "abstract for a paper."
                )
            },
            'title': {
                'type': 'acdd',
                'height': '80px',
                'description': (
                    "A short phrase or sentence describing the dataset. In "
                    "many discovery systems, the title will be displayed in "
                    "the results list from a search, and therefore should be "
                    "human readable and reasonable to display in a list of "
                    "such names."
                )
            },
            'contributors_citation': {
                'type': 'accd',
                'height': '80px',
                'description': (
                "A list, separated by commas, of contributors to the dataset. "
                "These contributors will be used to generate the citation at "
                "the end of the xml metadata document. Please use Last Name(.) "
                "First Initial(.,) followed by First Initial(.) Last Name format "
                "(ex: Smith, A., B. Liu, C. Ahmed...)."
                )
            },
            'link_citation': {
                'type': 'accd',
                'height': '80px',
                'description': (
                "Link to where data are archived for public access. This will be "
                "included in the metadata xml citation as 'Link_Note'."
                )
            }
        }
        
        for key, props in properties.items():
            layout = widgets.Layout(
                    width=HTML_COLUMN_WIDTH, border=COMMON_BORDER
            )
            # 1st column is the descriptive HTML
            accordion = widgets.Accordion(
                        children=[widgets.HTML(f"<p>{props['description']}</p>")],
                        titles=(f"{key}",),
                        layout=layout) # widgets.HTML(text, layout=layout)

            # populate the widget with the attribute value from the historical
            # file, if the attribute exists exists.
            if key == 'history':
                # history doesn't need to be edited
                attr_val = f"{dt.datetime.now()}: PMEL xCO2 notebook"
            elif key == 'standard_name_vocabulary':
                # standard_name_vocabulary doesn't need to be edited
                attr_val = "CF Standard Name Table v76"
            elif key == 'contributors_citation':
                # list of contributors, use config?
                attr_val = ', '.join(self.config['metadata'].get('contributors_citation', ''))
            elif key == 'link_citation':
                attr_val = self.config['metadata'].get('link_citation', '')
            else:
                try:
                    with xr.open_dataset(self.historical_ncfile) as ds:
                        attr_val = getattr(ds, key)
                except Exception:
                    # AttributeError if the netcdf file doesn't have the
                    # attribute
                    # TypeError if the netCDF file doesn't exist
                    attr_val = ''

            # 2nd column are the controls
            self.acdd_attr_text_controls[key] = widgets.Textarea(
                value=attr_val,
                layout=widgets.Layout(width='100%', height=props['height'])
            )
            layout = widgets.Layout(
                width=CONTROL_COLUMN_WIDTH, border=COMMON_BORDER
            )
            controls_box = widgets.HBox(
                [self.acdd_attr_text_controls[key]], layout=layout
            )

            row = widgets.HBox([accordion, controls_box], layout=layout)

            self.gui_rows.append(row)

    def setup_pi_list_controls(self):
        """
        Present an input box for entering the PI list.
        """
        # 1st column is the descriptive HTML
        text = '<h3><b>PI List</b></h3>'
        layout = widgets.Layout(width=HTML_COLUMN_WIDTH, border=COMMON_BORDER)
        html = widgets.HTML(text, layout=layout)

        # 2nd column are the controls for the PI details.
        pi_children = []
        for j in range(max(self.num_pis, len(self.config['metadata']['pi_list']))):
            pi_entry = self.create_person_details()
            pi_children.append(pi_entry)
        layout = widgets.Layout(
            width=CONTROL_COLUMN_WIDTH, border=COMMON_BORDER
        )
        pi_tab = widgets.Tab(layout=layout)
        pi_tab.children = pi_children
        pi_tab.titles = [f'PI {i + 1}' for i in range(len(pi_children))]

        # Fill in the details of the PIs that we know about.
        pi_s = self.config['metadata']['pi_list']
        for idx, pi in enumerate(pi_s):
            gui = pi_tab.children[idx]
            gui.children[0].children[1].value = pi.get('last_name', '')
            gui.children[1].children[1].value = pi.get('first_name', '')
            gui.children[2].children[1].value = pi.get('title', '')

            gui.children[3].children[1].value = pi.get('organization', '')
            gui.children[4].children[1].value = pi.get('address', '')
            gui.children[5].children[1].value = pi.get('phone', '')
            gui.children[6].children[1].value = pi.get('email', '')

        all_pis_row = widgets.HBox([html, pi_tab], layout=layout)

        self.pi_list = pi_tab

        self.gui_rows.append(all_pis_row)

    def setup_qcer_controls(self):
        """
        Present editable text boxes for the QCer details.
        """
        # 1st column is the descriptive HTML
        text = (
            '<h3><b>QC Operator</b></h3>'
            '<p> Enter the details for the individual running the QC process '
            '</p>'
        )
        layout = widgets.Layout(
            width=HTML_COLUMN_WIDTH, border=COMMON_BORDER
        )
        html = widgets.HTML(text, layout=layout)

        # 2nd column are the controls
        box = self.create_person_details()

        # Store references to the text widgets as being associated with the
        # QCer.
        self.qcer['last_name'] = box.children[0].children[1]
        self.qcer['first_name'] = box.children[1].children[1]
        self.qcer['title'] = box.children[2].children[1]
        self.qcer['organization'] = box.children[3].children[1]
        self.qcer['address'] = box.children[4].children[1]
        self.qcer['phone'] = box.children[5].children[1]
        self.qcer['email'] = box.children[6].children[1]

        layout = widgets.Layout(width=CONTROL_COLUMN_WIDTH, border=COMMON_BORDER)
        row = widgets.HBox([html, box], layout=layout)

        self.gui_rows.append(row)

    def setup_vessel_id_controls(self):
        """
        Present an editable text box for the vessel ID.
        """
        # 1st column is the descriptive HTML
        text = '<h3><b>Vessel ID</b></h3>'
        layout = widgets.Layout(
            width=HTML_COLUMN_WIDTH, border=COMMON_BORDER
        )
        html = widgets.HTML(text, layout=layout)

        # 2nd column are the controls
        self.vessel_id_text = widgets.Text()
        layout = widgets.Layout(
            width=CONTROL_COLUMN_WIDTH, border=COMMON_BORDER
        )
        controls_box = widgets.HBox([self.vessel_id_text], layout=layout)

        row = widgets.HBox([html, controls_box], layout=layout)

        self.gui_rows.append(row)
    
    def setup_stationary_mobile_controls(self):
        """
        Present slider setting whether deployment is stationary or mobile
        """
        # 1st column is the decriptive HTML
        text = '<h4><b>Stationary/Mobile Platform</b></h4>'
        layout = widgets.Layout(
            width=HTML_COLUMN_WIDTH, border=COMMON_BORDER
        )
        html = widgets.HTML(text, layout=layout)

        # 2nd column are the controls
        options = ['Stationary', '', 'Mobile']
        self.stationary_mobile = widgets.SelectionSlider(
                                        options=options,
                                        value='',
                                        orientation='horizontal',
                                        readout=True
                                        )
        layout = widgets.Layout(
            width=CONTROL_COLUMN_WIDTH, border=COMMON_BORDER
        )
        controls_box = widgets.HBox([self.stationary_mobile], layout=layout)

        row = widgets.HBox([html, controls_box], layout=layout)

        self.gui_rows.append(row)
        

    def create_person_details(self):

        last_name_label = widgets.Label(value=r'Last Name')
        last_name_text = widgets.Text()
        last_name_row = widgets.HBox([last_name_label, last_name_text])

        first_name_label = widgets.Label(value='First Name')
        first_name_text = widgets.Text()
        first_name_row = widgets.HBox([first_name_label, first_name_text])

        title_label = widgets.Label(value='Title')
        title_text = widgets.Text()
        title_row = widgets.HBox([title_label, title_text])

        organization_label = widgets.Label(value='Organization')
        organization_text = widgets.Text()
        organization_row = widgets.HBox([
            organization_label, organization_text
        ])

        address_label = widgets.Label(value='Address')
        address_text = widgets.Text()
        address_row = widgets.HBox([address_label, address_text])

        phone_label = widgets.Label(value='Phone')
        phone_text = widgets.Text()
        phone_row = widgets.HBox([phone_label, phone_text])

        email_label = widgets.Label(value='Email')
        email_text = widgets.Text()
        email_row = widgets.HBox([email_label, email_text])

        items = [
            last_name_row, first_name_row, title_row, organization_row,
            address_row, phone_row, email_row
        ]
        layout = widgets.Layout(border=COMMON_BORDER)
        form = widgets.VBox(items, layout=layout)
        return form

    def gather_kwargs(self):
        """
        Gather all the values currently set by the GUI.  They are to be passed
        into the metadata writer program and the socat writer program.
        """
        if self.stationary_mobile.value == '':
            raise NoMobileSelection("User needs to select whether data is from a stationary or mobile platform")
        
        pi_list = []
        for pi_gui_row in self.pi_list.children:

            # Each pi_gui is a VBox that has the 5 items for the PI info.
            pi = {
                'last_name': pi_gui_row.children[0].children[1].value,
                'first_name': pi_gui_row.children[1].children[1].value,
                'title': pi_gui_row.children[2].children[1].value,
                'organization': pi_gui_row.children[3].children[1].value,
                'address': pi_gui_row.children[4].children[1].value,
                'phone': pi_gui_row.children[5].children[1].value,
                'email': pi_gui_row.children[6].children[1].value,
            }

            if any(pi.values()):
                pi_list.append(pi)

        qcer = {
            'last_name': self.qcer['last_name'].value,
            'first_name': self.qcer['first_name'].value,
            'title': self.qcer['title'].value,
            'organization': self.qcer['organization'].value,
            'address': self.qcer['address'].value,
            'phone': self.qcer['phone'].value,
            'email': self.qcer['email'].value,
        }
        kwargs = {
            'pi_list': pi_list,
            'qcer': qcer,
            'vessel_id': self.vessel_id_text.value,
        }

        # Add other attributes (usually but not always ACDD) that have GUI text
        # controls.
        for attr_name in [
            'creator_name', 'creator_type', 'creator_email', 'creator_url',
            'history', 'infoUrl', 'institution', 'keywords', 'license',
            'references', 'standard_name_vocabulary', 'summary', 'title',
            'contributors_citation', 'link_citation'
        ]:
            kwargs[attr_name] = self.acdd_attr_text_controls[attr_name].value
        
        kwargs['stationary_mobile'] = self.stationary_mobile.value.lower()
        
        return kwargs


class NoMobileSelection(Exception):
    def __init__(self, message):
        self.message = message