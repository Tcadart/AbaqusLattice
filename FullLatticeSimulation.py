# Version python 3.9.7
# ----------------------------------------------------------------------------
# Created By  : Thomas Cadart
# Created Date: 30/06/2023
# version ='1.0'
# ---------------------------------------------------------------------------
"""
Code to create a lattice in Abaqus with the submodule Lattice
Then prepare the simulation in Abaqus
"""
import numpy as np

from AbaqusLattice.abaqus import *
from abaqusConstants import *
import regionToolset


from Lattice import *
import re
from Materials import *

from Lattice_description import *


# *******************************************************************************************************************
# *******************************************************************************************************************

#                                           Functions

# *******************************************************************************************************************
# *******************************************************************************************************************

def CreateModel(name_model):
    """
    Create a model in Abaqus

    Parameters
    ----------
    name_model : str
        Name of the model.
    """
    # Create Model
    mdb.Model(name=name_model, modelType=STANDARD_EXPLICIT)


def CreatePart(name_model, name_Part):
    """
    Create a part in Abaqus for beam lattices

    Parameters
    ----------
    name_model : str
        Name of the model.
    name_Part : str
        Name of the part.
    """
    #Create Part
    s1 = mdb.models[name_model].ConstrainedSketch(name='__profile__',
                                                  sheetSize=200.0)
    g, v, d, c = s1.geometry, s1.vertices, s1.dimensions, s1.constraints
    s1.setPrimaryObject(option=STANDALONE)
    s1.Line(point1=(0.0, 0.0), point2=(0.0, 5.0))
    s1.VerticalConstraint(entity=g[2], addUndoState=False)
    p = mdb.models[name_model].Part(name=name_Part, dimensionality=THREE_D,
                                    type=DEFORMABLE_BODY)
    p = mdb.models[name_model].parts[name_Part]
    p.BaseWire(sketch=s1)
    s1.unsetPrimaryObject()
    p = mdb.models[name_model].parts[name_Part]
    del mdb.models[name_model].sketches['__profile__']
    # Delete Part
    del p.features['Wire-1']


def CreateNodes(name_model, name_Part):
    """
    Create nodes of lattice in Abaqus

    Parameters
    ----------
    name_model : str
        Name of the model.
    name_Part : str
        Name of the part.
    """
    p = mdb.models[name_model].parts[name_Part]
    for i in range(len(lattice.nodes)):
        p.DatumPointByCoordinate(coords=(lattice.nodes[i][1], lattice.nodes[i][2], lattice.nodes[i][3]))


def CreateBeams(name_model, name_Part):
    """
    Create beams of lattice in Abaqus

    Parameters
    ----------
    name_model : str
        Name of the model.
    name_Part : str
        Name of the part.
    """
    p = mdb.models[name_model].parts[name_Part]
    d2 = p.datums
    idx_default = 2
    beam_points = []
    for i in range(len(lattice.beams)):
        # Debug when element index is greater than 999
        idx1 = 3 if int(lattice.beams[i][1]) + 2 > 999 else idx_default
        idx2 = 3 if int(lattice.beams[i][2]) + 2 > 999 else idx_default

        datum1 = d2[int(lattice.beams[i][1]) + idx1]
        datum2 = d2[int(lattice.beams[i][2]) + idx2]

        beam_points.append((datum1, datum2))

    p.WirePolyLine(points=beam_points, mergeType=IMPRINT, meshable=ON)


def SetAbaqusWindows(name_model, name_Part):
    p = mdb.models[name_model].parts[name_Part]
    session.viewports['Viewport: 1'].setValues(displayedObject=p)


def Assembly_beam(name_model, name_Part, name_Assembly):
    a1 = mdb.models[name_model].rootAssembly
    a1.DatumCsysByDefault(CARTESIAN)
    p = mdb.models[name_model].parts[name_Part]
    a1.Instance(name=name_Assembly, part=p, dependent=ON)


def Assembly_beam_Surface(name_model, name_Part, name_surface):
    # Assembly 2 parts and move surface at good position
    a1 = mdb.models[name_model].rootAssembly
    p = mdb.models[name_model].parts[name_Part]
    name_Part_Assembly = name_Part + '-1'
    a1.Instance(name=name_Part_Assembly, part=p, dependent=ON)
    p = mdb.models[name_model].parts[name_surface]
    name_surface_Assembly = name_surface + '-1'
    a1.Instance(name=name_surface_Assembly, part=p, dependent=ON)
    a1.translate(instanceList=(name_surface_Assembly,), vector=(0.0, 0.0, lattice.zMax + 0.1 * lattice.zMax))
    return name_Part_Assembly, name_surface_Assembly


def CreateSet(name_model, lattice, name_Set, Position, node_data, name_Assembly):
    """
    Create a set of nodes at the extremity of the lattice

    Parameters
    ----------
    name_model : str
        Name of the model.
    lattice : Lattice
        Lattice object.
    name_Set : str
        Name of the set.
    Position : str
        Position of the set. (x+,x-,y+,y-,z+,z-)
    node_data : list
        List of nodes.
    name_Assembly : str
        Name of the assembly.
    """
    #Traitement Position
    if 'x' in Position:
        Direction = 1
        if '+' in Position:
            valselected = lattice.xMax
        else:
            valselected = lattice.xMin
    elif 'y' in Position:
        Direction = 2
        if '+' in Position:
            valselected = lattice.yMax
        else:
            valselected = lattice.yMin
    elif 'z' in Position:
        Direction = 3
        if '+' in Position:
            valselected = lattice.zMax
        else:
            valselected = lattice.zMin
    m = mdb.models[name_model]
    a = m.rootAssembly
    v1 = a.instances[name_Assembly].vertices
    verts1 = []
    for i in range(len(node_data)):
        if node_data[i][Direction] == valselected:
            verts1.append(v1.findAt(((node_data[i][1], node_data[i][2], node_data[i][3]),), ))
    a.Set(vertices=verts1, name=name_Set)


def mesh_Part(name_model, name_Part, mesh_size):
    """
    Mesh a part in Abaqus

    Parameters
    ----------
    name_model : str
        Name of the model.
    name_Part : str
        Name of the part.
    mesh_size : float
        Size of the mesh.
    """
    p = mdb.models[name_model].parts[name_Part]
    p.seedPart(size=mesh_size, deviationFactor=0.1, minSizeFactor=0.1)
    p.generateMesh()


def getUniqueRadius():
    """
    Get unique radius of the lattice

    Returns
    -------
    list
        List of unique radius
    """
    uniqueRadius = list(set(lattice.radius))
    return uniqueRadius


def Create_Beam_Profile_Mod(name_model, name_Part, VectorOrientation, name_region, name_Beam_Profile):
    """
    Create a beam profile for modified beams in Abaqus

    Parameters
    ----------
    name_model : str
        Name of the model.
    name_Part : str
        Name of the part.
    VectorOrientation : list
        Vector orientation.
    name_region : str
        Name of the region.
    name_Beam_Profile : str
        Name of the beam profile.
    """
    # Beam Section Orientation
    p = mdb.models[name_model].parts[name_Part]
    Region_mid, Region_Ext = selectBeamRegion(name_region)
    p.assignBeamSectionOrientation(region=Region_mid, method=N1_COSINES,
                                   n1=(VectorOrientation[0], VectorOrientation[1], VectorOrientation[2]))
    p.assignBeamSectionOrientation(region=Region_Ext, method=N1_COSINES,
                                   n1=(VectorOrientation[0], VectorOrientation[1], VectorOrientation[2]))
    # Beam Profile creation
    uniqueRadius = getUniqueRadius()
    name = []
    for i in range(len(uniqueRadius)):
        mdb.models[name_model].CircularProfile(name=name_Beam_Profile + '_' + str(uniqueRadius[i]), r=uniqueRadius[i])
        name.append(name_Beam_Profile + '_' + str(uniqueRadius[i]))
    return name, Region_mid, Region_Ext


def Create_Beam_Profile(name_model, name_Part, VectorOrientation, name_region, name_Beam_Profile):
    """
    Create a beam profile in Abaqus

    Parameters
    ----------
    name_model : str
        Name of the model.
    name_Part : str
        Name of the part.
    VectorOrientation : list
        Vector orientation.
    name_region : str
        Name of the region.
    name_Beam_Profile : str
        Name of the beam profile.
    """
    # Beam Section Orientation
    p = mdb.models[name_model].parts[name_Part]
    AllBeams = selectBeamRegion(name_region)
    p.assignBeamSectionOrientation(region=AllBeams, method=N1_COSINES,
                                   n1=(VectorOrientation[0], VectorOrientation[1], VectorOrientation[2]))
    # Beam Profile creation
    uniqueRadius = getUniqueRadius()
    name = []
    for i in range(len(uniqueRadius)):
        mdb.models[name_model].CircularProfile(name=name_Beam_Profile + '_' + str(uniqueRadius[i]), r=uniqueRadius[i])
        name.append(name_Beam_Profile + '_' + str(uniqueRadius[i]))
    return name, AllBeams


def selectBeamRegion(name_region):
    """
    Select the region of the structure to apply the beam section

    Parameters
    ----------
    name_region : str
        Name of the region. (AllBeams, BeamMid, BeamMod, X1, X2, X3, Y1, Y2, Y3, Z1, Z2, Z3)
    """
    p = mdb.models[name_model].parts[name_Part]
    e = p.edges
    if name_region == 'AllBeams':  #Traitement all beams
        edges = e.getByBoundingBox(xMin=lattice.xMin, yMin=lattice.yMin, zMin=lattice.zMin, xMax=lattice.xMax,
                                   yMax=lattice.yMax, zMax=lattice.zMax)
        Region = p.Set(edges=edges, name=name_region)
    elif name_region == 'BeamMod':
        edges = e.getByBoundingBox(xMin=lattice.xMin, yMin=lattice.yMin, zMin=lattice.zMin, xMax=lattice.xMax,
                                   yMax=lattice.yMax, zMax=lattice.zMax)
        Region = p.Set(edges=edges, name='AllBeams')
        # For normal beams
        edges_mid = []
        for i in range(len(lattice.beams)):
            if lattice.beams[i][3] == 0:  #Check type of beam Center or modified
                edges_mid.append(e.findAt(((lattice.nodes[lattice.beams[i][1]][1] + (
                        lattice.nodes[lattice.beams[i][2]][1] - lattice.nodes[lattice.beams[i][1]][1]) / 2,
                                            lattice.nodes[lattice.beams[i][1]][2] + (
                                                    lattice.nodes[lattice.beams[i][2]][2] -
                                                    lattice.nodes[lattice.beams[i][1]][2]) / 2,
                                            lattice.nodes[lattice.beams[i][1]][3] + (
                                                    lattice.nodes[lattice.beams[i][2]][3] -
                                                    lattice.nodes[lattice.beams[i][1]][3]) / 2),), ))
        region_mid = p.Set(edges=edges_mid, name='BeamMid')
        # For Modified beams
        p = mdb.models[name_model].parts[name_Part]
        region_ext = p.SetByBoolean(name='BeamMod', operation=DIFFERENCE, sets=(p.sets['AllBeams'], p.sets['BeamMid'],))
        return region_mid, region_ext
    else:  # Traitement couche par couche ################## Probleme lors de poutres qui apparraisent dans 2 couche differentes Il faut un traitement different
        couche_number = int(re.search(r'\d+', name_region).group())
        if 'X' in name_region:
            edges = e.getByBoundingBox(
                xMin=lattice.xMax - ((lattice.numCellsX + 1 - couche_number) * lattice.cellSizeX), yMin=lattice.yMin,
                zMin=lattice.zMin, xMax=lattice.xMax - ((lattice.numCellsX - couche_number) * lattice.cellSizeX),
                yMax=lattice.yMax, zMax=lattice.zMax)
            Region = p.Set(edges=edges, name=name_region)
        if 'Y' in name_region:
            edges = e.getByBoundingBox(xMin=lattice.xMin, yMin=lattice.yMax - (
                    (lattice.numCellsY + 1 - couche_number) * lattice.cellSizeY), zMin=lattice.zMin,
                                       xMax=lattice.xMax,
                                       yMax=lattice.yMax - ((lattice.numCellsY - couche_number) * lattice.cellSizeY),
                                       zMax=lattice.zMax)
            Region = p.Set(edges=edges, name=name_region)
        if 'Z' in name_region:
            edges = e.getByBoundingBox(xMin=lattice.xMin, yMin=lattice.yMin, zMin=lattice.zMax - (
                    (lattice.numCellsZ + 1 - couche_number) * lattice.cellSizeZ), xMax=lattice.xMax,
                                       yMax=lattice.yMax,
                                       zMax=lattice.zMax - ((lattice.numCellsZ - couche_number) * lattice.cellSizeZ))
            Region = p.Set(edges=edges, name=name_region)
    return Region


def create_material(name_model, Material_Type, Material_Carac):
    """
    Create a material in Abaqus with the given characteristics of class Material in Lattice project

    Parameters
    ----------
    name_model : str
        Name of the model.
    Material_Type : int
        Type of mateial
    Material_Carac : int
        Material characteristics.
    """
    m = MatProperties(Material_Type, Material_Carac)
    mdb.models[name_model].Material(name=m.name)
    mdb.models[name_model].materials[m.name].Density(table=((m.density,),))
    mdb.models[name_model].materials[m.name].Elastic(table=((m.elastic[0], m.elastic[1]),))
    if Material_Carac == 1 and Material_Type == 0:
        mdb.models[name_model].materials[m.name].Plastic(scaleStress=None, table=m.plastic)
    elif Material_Carac == 1 and Material_Type == 4:
        mdb.models[name_model].materials[m.name].Plastic(scaleStress=None, table=m.plastic)
    elif Material_Carac == 1 and Material_Type == 3:
        mdb.models[name_model].materials[m.name].Plastic(hardening=JOHNSON_COOK,
                                                         scaleStress=None, table=(m.plastic,))
    return m.name


def Create_Beam_Section(name_model, name_Section, name_material, name_Beam_Profile, Region):
    """
    Create a beam section in Abaqus

    Parameters
    ----------
    name_model : str
        Name of the model.
    name_Section : str
        Name of the section.
    name_material : str
        Name of the material.
    name_Beam_Profile : str
        Name of the beam profile.
    Region : str
        Name of the region.
    """
    # Beam Section creation
    mdb.models[name_model].BeamSection(name=name_Section, integration=DURING_ANALYSIS,
                                       poissonRatio=0.0, profile=name_Beam_Profile, material=name_material,
                                       temperatureVar=LINEAR, consistentMassMatrix=False)
    # Beam assignment
    p = mdb.models[name_model].parts[name_Part]
    p.SectionAssignment(region=Region, sectionName=name_Section, offset=0.0,
                        offsetType=MIDDLE_SURFACE, offsetField='',
                        thicknessAssignment=FROM_SECTION)


def Create_Job(name_Job, name_model):
    """
    Create a job in Abaqus

    Parameters
    ----------
    name_Job : str
        Name of the job.
    name_model : str
        Name of the model.
    """
    # Create a job
    mdb.Job(name=name_Job, model=name_model, description='', type=ANALYSIS,
            atTime=None, waitMinutes=0, waitHours=0, queue=None, memory=90,
            memoryUnits=PERCENTAGE, getMemoryFromAnalysis=True,
            explicitPrecision=SINGLE, nodalOutputPrecision=SINGLE, echoPrint=OFF,
            modelPrint=OFF, contactPrint=OFF, historyPrint=OFF, userSubroutine='',
            scratch='', resultsFormat=ODB, numThreadsPerMpiProcess=1,
            multiprocessingMode=DEFAULT, numCpus=1, numGPUs=0)


def Submit_Job(name_Job, name_model):
    """
    Submit a job in Abaqus

    Parameters
    ----------
    name_Job : str
        Name of the job.
    name_model : str
        Name of the model.
    """
    # Submit and wait
    job1 = mdb.Job(name=name_Job, model=name_model)
    job1.submit()
    # job1.waitForCompletion()


def Create_Step(name_model, name_step, name_previous_step, AnalysisType):
    """
    Create a step in the model

    Parameters
    ----------
    name_model : str
        Name of the model.
    name_step : str
        Name of the step.
    name_previous_step : str
        Name of the previous step.
    AnalysisType : int
        Type of analysis. (1: Static, 2: Implicit)
    """
    if AnalysisType == 1:
        # mdb.models[name_model].StaticStep(name=name_step, previous=name_previous_step)
        mdb.models[name_model].StaticStep(name=name_step, previous=name_previous_step, nlgeom=ON,
                                          stabilizationMagnitude=0.0002,
                                          stabilizationMethod=DISSIPATED_ENERGY_FRACTION,
                                          continueDampingFactors=False, adaptiveDampingRatio=0.05, initialInc=0.1)
    elif AnalysisType == 2:
        mdb.models[name_model].StaticStep(name=name_step, previous=name_previous_step, nlgeom=ON)


def Create_BC_Fixed(name_model, name_step, name_set):
    a = mdb.models[name_model].rootAssembly
    region = region = a.sets[name_set]
    mdb.models[name_model].EncastreBC(name='Fixed', createStepName=name_step, region=region, localCsys=None)


def Create_Loads(name_model, name_step, name_set, name_load, vector_load):
    a = mdb.models[name_model].rootAssembly
    region = a.sets[name_set]
    mdb.models[name_model].DisplacementBC(name=name_load, createStepName=name_step,
                                          region=region, u1=vector_load[0], u2=vector_load[1], u3=vector_load[2],
                                          ur1=UNSET, ur2=UNSET, ur3=UNSET,
                                          amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='',
                                          localCsys=None)


def Create_Loads_Surface(name_model, name_step, name_surface_Assembly, name_load, vector_load):
    a = mdb.models[name_model].rootAssembly
    r1 = a.instances[name_surface_Assembly].referencePoints
    refPoints1 = (r1[2],)
    region = regionToolset.Region(referencePoints=refPoints1)
    mdb.models[name_model].DisplacementBC(name=name_load, createStepName=name_step,
                                          region=region, u1=vector_load[0], u2=vector_load[1], u3=vector_load[2],
                                          ur1=UNSET, ur2=UNSET, ur3=UNSET,
                                          amplitude=UNSET, fixed=OFF, distributionType=UNIFORM, fieldName='',
                                          localCsys=None)


def Create_GetReactionForce(name_model, name_step, name_set):
    regionDef = mdb.models[name_model].rootAssembly.sets[name_set]
    mdb.models[name_model].HistoryOutputRequest(name='Reaction_Force',
                                                createStepName=name_step, variables=('RF1', 'RF2', 'RF3'),
                                                region=regionDef,
                                                sectionPoints=DEFAULT, rebar=EXCLUDE)


def Create_GetDisplacement(name_model, name_step, name_set):
    regionDef = mdb.models[name_model].rootAssembly.sets[name_set]
    mdb.models[name_model].HistoryOutputRequest(name='Displacement',
                                                createStepName=name_step, variables=('U1', 'U2', 'U3'),
                                                region=regionDef,
                                                sectionPoints=DEFAULT, rebar=EXCLUDE)


def Delete_output_default(name_model):
    del mdb.models[name_model].historyOutputRequests['H-Output-1']
    mdb.models[name_model].fieldOutputRequests['F-Output-1'].setValues(variables=('S', 'PE', 'PEEQ', 'U', 'RF'))


def visualizationSimulation(name_Job):
    o3 = session.openOdb(name='D:/travail_Abaqus/Lattice/' + name_Job + '.odb')
    session.viewports['Viewport: 1'].setValues(displayedObject=o3)
    session.viewports['Viewport: 1'].makeCurrent()
    session.viewports['Viewport: 1'].odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
    session.viewports['Viewport: 1'].odbDisplay.setFrame(step=0, frame=0)
    session.viewports['Viewport: 1'].odbDisplay.setFrame(step=0, frame=1)


def constructLatticeAbaqus(name_model, name_Part, name_Assembly, Lattice_Type, MethodSim):
    """
    Construct the lattice in Abaqus

    Parameters
    ----------
    name_model : str
        Name of the model.
    name_Part : str
        Name of the part.
    name_Assembly : str
        Name of the assembly.
    Lattice_Type : int
        Type of lattice.
    MethodSim : int
        Method of simulation. (0: Normal, 1: Modified)
    """
    CreateModel(name_model)
    CreatePart(name_model, name_Part)
    CreateNodes(name_model, name_Part)
    CreateBeams(name_model, name_Part)
    mesh_Part(name_model, name_Part, 0.087)
    if MethodSim == 1:
        name_region = 'BeamMod'
        name_Beam_Profile = 'Circ'
        name_Beam_Profile, Region_mid, Region_Ext = Create_Beam_Profile_Mod(name_model, name_Part,
                                                                            getVectorOrientation(Lattice_Type),
                                                                            name_region, name_Beam_Profile)
    elif MethodSim == 0:
        name_region = 'AllBeams'
        name_Beam_Profile = 'Circ'
        name_Beam_Profile, AllBeam = Create_Beam_Profile(name_model, name_Part, getVectorOrientation(Lattice_Type),
                                                         name_region, name_Beam_Profile)

    name_material = create_material(name_model, 4, 1)

    if MethodSim == 1:
        Create_Beam_Section(name_model, 'CircBeam', name_material, name_Beam_Profile[1], Region_mid)
        Create_Beam_Section(name_model, 'CircBeammod', name_material, name_Beam_Profile[0], Region_Ext)
    elif MethodSim == 0:
        Create_Beam_Section(name_model, 'CircBeam', name_material, name_Beam_Profile[0], AllBeam)




def getReactionForce(name_Job):
    # Create file with all reaction force data
    file_path = '/abaqus.rpt'
    odb = session.odbs['D:/travail_Abaqus/Lattice/' + name_Job + '.odb']
    session.writeFieldReport(fileName=file_path, append=OFF,
                             sortItem='Node Label', odb=odb, step=0, frame=1, outputPosition=NODAL,
                             variable=(('RF', NODAL),), stepFrame=SPECIFY)
    reactionforceData = []
    with open(file_path, 'r') as file:
        is_data_section = False  # Indicateur pour savoir si nous sommes dans la section des donnees
        for line in file:
            # Recherche de la ligne qui indique le debut des donnees des noeuds
            if "Node Label" in line:
                is_data_section = True
                continue
            if "Minimum" in line:
                is_data_section = False
                continue
            if is_data_section:
                # Separation des valeurs en utilisant les espaces comme separateurs
                values = line.split()
                if len(values) == 5 and float(values[1]) != 0:  # Nous nous attendons a 4 valeurs numeriques par ligne
                    node_label = int(values[0])
                    rf_magnitude = float(values[1])
                    rf_rf1 = float(values[2])
                    rf_rf2 = float(values[3])
                    rf_rf3 = float(values[4])
                    reactionforceData.append((node_label, rf_magnitude, rf_rf1, rf_rf2, rf_rf3))
    fixedNodeReactionForce = []
    reactionForceZ = 0
    for i in range(len(reactionforceData)):
        if reactionforceData[i][4] > 0:
            fixedNodeReactionForce.append(reactionforceData[i])
            reactionForceZ += reactionforceData[i][4]
    print(reactionForceZ)
    return reactionForceZ


def get_result(name_Job, name_step):
    odb = openOdb(name_Job + '.odb')
    historyRegions = odb.steps[name_step].historyRegions

    dataRF = {'RF1': [], 'RF2': [], 'RF3': []}
    dataU = {'U1': [], 'U2': [], 'U3': []}
    dataTime = []

    for key in historyRegions.keys():
        historyRegion = historyRegions[key]

        # Traitement pour RF1, RF2, RF3
        for rf_key in dataRF.keys():
            try:
                rf_data = historyRegion.historyOutputs[rf_key].data
                if not dataRF[rf_key]:  # Si la liste est vide
                    dataRF[rf_key] = [value for _, value in rf_data]
                else:
                    for i, (_, value) in enumerate(rf_data):
                        dataRF[rf_key][i] += value
            except KeyError:
                pass

        # Traitement pour U1, U2, U3
        for u_key in dataU.keys():
            try:
                u_data = historyRegion.historyOutputs[u_key].data
                if not dataU[u_key]:  # Si la liste est vide
                    dataU[u_key] = [value for _, value in u_data]
                    if u_key == 'U1':  # Assurer que dataTime est seulement rempli une fois
                        dataTime = [time for time, _ in u_data]
            except KeyError:
                pass

    return dataRF, dataU, dataTime


def save_result(Lattice_Type, number_cell, AnalysisType, MethodSim, dataRF, dataU, dataTime):
    filename = Type_lattice(Lattice_Type) + "_" + str(number_cell) + str(AnalysisType) + str(MethodSim) + ".txt"

    with open(filename, "w") as f:
        for rf_key in ['RF1', 'RF2', 'RF3']:
            rf_data_str = np.array2string(np.array(dataRF[rf_key]), separator=',')
            f.write(rf_data_str + "\n")

        for u_key in ['U1', 'U2', 'U3']:
            u_data_str = np.array2string(np.array(dataU[u_key]), separator=',')
            f.write(u_data_str + "\n")

        time_data_str = np.array2string(np.array(dataTime), separator=',')
        f.write(time_data_str + "\n")

def delete_all_models():
    model_names = list(mdb.models.keys())
    for name in model_names:
        if name != 'Model-1':  # 'Model-1' basic model
            del mdb.models[name]


#*******************************************************************************************************************
#*******************************************************************************************************************

#Variables

#*******************************************************************************************************************
#*******************************************************************************************************************

name_model = 'BCC_beammod'
name_Job = 'Job_1'
name_Part = 'Lattice_Part'
name_Assembly = 'Lattice_assembly'

Radius = 1.5
cell_size = 10
cell_size_X = cell_size
cell_size_Y = cell_size
cell_size_Z = cell_size
number_cell = 3
number_cell_X = 2
number_cell_Y = 2
number_cell_Z = 2

Lattice_Type = 0
# 0 => BCC
# 1 => Octet 
# 2 => OctetExt 
# 3 => OctetInt 
# 4 => BCCZ 
# 5 => Cubic 
# 6 => OctahedronZ 
# 7 => OctahedronZcross 
# 8 => Kelvin
# 9 => Cubic formulation 2 (centered)
# 10 => Auxetic

# Gradient on cell dimensions
GradDimRule = 'constant'
GradDimDirection = [1, 0, 0]
GradDimParameters = [1.5, 0.0, 2.0]  #Float
# Gradient on radius of beams
GradRadRule = 'constant'
GradRadDirection = [0, 0, 1]
GradRadParameters = [1.0, 0.0, 2.0]
#Gradient Rule
# - constant
# - linear
# - parabolic
# - sinusoide
# - exponential

Multimat = 0  # Not coded yet
# 0 -> materiaux
# 1 -> multimat par couche
GradMaterialDirection = 1  # 1:X / 2:Y / 3:Z

MethodSim = 1
# 0 No modification
# 1 Node Modification


# Gradient properties
gradDimProperty = [GradDimRule, GradDimDirection, GradDimParameters]
gradRadiusProperty = [GradRadRule, GradRadDirection, GradRadParameters]
gradMatProperty = [Multimat, GradMaterialDirection]

AnalysisType = 1
# 0 Modelisation lattice only
# 1 Compression Z static
compressionPourcent = 20

# Generate data from lattice
lattice = Lattice(cell_size_X, cell_size_Y, cell_size_Z, number_cell_X, number_cell_Y, number_cell_Z, Lattice_Type,
                  Radius, gradRadiusProperty, gradDimProperty, gradMatProperty, MethodSim, False)
# Load vector
displacementCompression = (lattice.zMax - lattice.zMin) * compressionPourcent / 100
load_vector = [0, 0, -displacementCompression]

constructLatticeAbaqus(name_model, name_Part, name_Assembly, Lattice_Type, MethodSim)

if AnalysisType == 1:
    # Create assembly for lattice 
    Assembly_beam(name_model, name_Part, name_Assembly)
    # Create set for fixed nodes and loaded nodes
    CreateSet(name_model, lattice, 'Fixed_nodes', "z-", lattice.nodes, name_Assembly)
    CreateSet(name_model, lattice, 'loaded_nodes', "z+", lattice.nodes, name_Assembly)
    # Create loading condition and submit job
    name_step = 'Step-1'
    Create_Step(name_model, name_step, 'Initial', AnalysisType)
    Create_BC_Fixed(name_model, 'Initial', 'Fixed_nodes')
    Create_Loads(name_model, name_step, 'loaded_nodes', 'Load_1', load_vector)
    Create_GetDisplacement(name_model, name_step, 'loaded_nodes')
    Create_GetReactionForce(name_model, name_step, 'Fixed_nodes')
    Delete_output_default(name_model)
    Submit_Job(name_Job, name_model)
    # visualizationSimulation(name_Job)
    # # dataRF3, dataU3, dataTime = get_result(name_Job,name_step)
    # dataRF, dataU, dataTime = get_result(name_Job,name_step)
    # save_result(latticeType, number_cell, AnalysisType, MethodSim, dataRF, dataU, dataTime)

# Affichage final
if AnalysisType == 0:
    # Visualization on abaqus
    SetAbaqusWindows(name_model, name_Part)
