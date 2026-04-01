"""
Configuration constants for IFC semantic splitting.
"""

# --------------------------------------------------------------------------- #
# Semantic category definitions
# --------------------------------------------------------------------------- #
# Each category maps to the IFC entity types that belong to it.
PIPING_TYPES = {"IfcPipeSegment", "IfcPipeFitting", "IfcValve"}

BUILDING_TYPES = {"IfcWall", "IfcSlab", "IfcBuildingElementProxy", "IfcBeam", "IfcColumn", "IfcRoof", "IfcMember"}

# Equipment entities to discard from all output models.
EQUIPMENT_TYPES = {
    # Mechanical / HVAC equipment
    "IfcHeatExchanger",
    "IfcTank",
    "IfcPump",
    "IfcFan",
    "IfcFilter",
    "IfcStackTerminal",
    "IfcCompressor",
    "IfcCondenser",
    "IfcCooledBeam",
    "IfcCoolingTower",
    "IfcEvaporativeCooler",
    "IfcEvaporator",
    "IfcBoiler",
    "IfcBurner",
    "IfcChiller",
    "IfcCoil",
    "IfcAirTerminal",
    "IfcAirTerminalBox",
    "IfcDamper",
    "IfcDuctSilencer",
    "IfcHumidifier",
    "IfcUnitaryEquipment",
    "IfcAirToAirHeatRecovery",
    # Plumbing / flow control
    "IfcInterceptor",
    "IfcFlowMeter",
    "IfcMedicalDevice",
    "IfcSanitaryTerminal",
    "IfcWasteTerminal",
    # Electrical / power
    "IfcElectricGenerator",
    "IfcElectricMotor",
    "IfcTransformer",
    "IfcMotorConnection",
    "IfcSwitchingDevice",
    "IfcProtectiveDevice",
    "IfcElectricDistributionBoard",
    # Fire protection
    "IfcFireSuppressionTerminal",
    # Generic energy conversion / distribution
    "IfcEngine",
    "IfcSolarDevice",
    "IfcTubeBundle",
    "IfcSpaceHeater",
}

# --------------------------------------------------------------------------- #
# Proximity thresholds (meters)
# --------------------------------------------------------------------------- #
# Building components within this distance are considered part of the same
# structural system (e.g. turbine building walls vs. containment).
BUILDING_PROXIMITY_THRESHOLD = 5.0