"""Building Generator"""

import Rhino.Geometry as rg
import Grasshopper
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path
import random
import math

class Building:
    class Building:
    """
    Procedural Building Generator for Rhino/Grasshopper

    This class generates a randomized building geometry using procedural methods, tailored for use
    within Rhino/Grasshopper via the RhinoCommon geometry library. It provides methods to generate 
    the site, building volume, storeys, slabs, walls, and columns, producing valid Brep objects 
    and DataTrees suitable for parametric workflows.

    Attributes:
        site (rg.Polyline or None): Polyline representing the building site.
        volume (rg.Brep or None): The main building volume as a Brep.
        storeys (list[rg.Brep]): Breps for each building storey.
        slabs (list[rg.Brep]): Breps for all slabs (floor, intermediate, roof).
        floor_slab (rg.Brep or None): Ground floor slab Brep.
        roof_slab (rg.Brep or None): Roof slab Brep.
        walls (list[list[rg.Brep]]): Nested list of wall Breps per storey.
        columns (list[list[rg.Brep]]): Nested list of column Breps per storey.

    Main Parameters (private):
        __target_area (float): Desired site area (m²).
        __min_length (float): Minimum side length for site and rectangles.
        __area_tolerance (float): Allowed deviation for site area.
        __min_height, __max_height (float): Min/max building height (m).
        __slab_thickness (float): Slab thickness (randomized per building).
        __min_wall_thickness, __max_wall_thickness (float): Wall thickness range (m).
        __max_wall_tilt_deg (float): Maximum wall tilt angle (degrees).
        __site_margin (float): Margin for offsetting site interior (m).

    Methods:
        generate_site(max_attempts=100): Creates a rectangular site polyline close to the target area.
        generate_volume(): Lofts between random base/roof curves to form the building volume.
        generate_storeys(): Splits volume into storeys by intersection with extruded planes.
        generate_slabs(): Generates slabs for each level and roof.
        generate_walls(): Produces 1–2 random wall Breps per storey as DataTree.
        generate_columns(): Creates 1–3 column Breps per storey as DataTree.
        to_gh_tree(nested_list): Utility to convert nested lists to Grasshopper DataTrees.

    Usage:
        Instantiate the class, call generation methods in sequence to procedurally construct
        a randomized building, then access the attributes for geometry output.
        
        Example:
            bldg = Building()
            bldg.generate_site()
            bldg.generate_volume()
            bldg.generate_storeys()
            bldg.generate_slabs()
            bldg.generate_walls()
            bldg.generate_columns()
    """
    
    def __init__(self):
        # --- Site and area parameters ---
        self.__target_area = 300.0         # Target site area in m²
        self.__min_length = 12.0           # Minimum site side length in meters
        self.__area_tolerance = 1.0        # Allowed deviation from target area

        # --- Building height parameters ---
        self.__min_height = 8.0            # Minimum building height (m)
        self.__max_height = 20.0           # Maximum building height (m)
        self.__height = None               # Actual building height (set later)

        # --- Slab parameters ---
        self.__min_slab_thickness = 0.15   # Minimum slab thickness (m)
        self.__max_slab_thickness = 0.35   # Maximum slab thickness (m)
        self.__slab_thickness = random.uniform(
            self.__min_slab_thickness, self.__max_slab_thickness
        )                                  # Random slab thickness for this building

        self.floor_slab = None             # Ground floor slab Brep
        self.slabs = []                    # Intermediate slab Breps
        self.roof_slab = None              # Roof slab Brep

        # --- Wall parameters ---
        self.__min_wall_thickness = 0.15   # Minimum wall thickness (m)
        self.__max_wall_thickness = 0.35   # Maximum wall thickness (m)
        self.__max_wall_tilt_deg = 5.0     # Maximum wall tilt in degrees

        self.walls = []                    # List of lists of wall Breps (per storey)

        # --- Site and volume geometry ---
        self.site = None                   # Site polyline
        self.__site_margin = 3.0           # Margin for offsetting inside site (m)
        self.volume = None                 # Building volume Brep

    def generate_site(self, max_attempts=100):
        """
        Generates a rectangular site polyline with area close to the target.
        Returns the site polyline or None if not successful.
        """
        for _ in range(max_attempts):
            # Randomly choose width, then compute height to match target area
            width = random.uniform(self.__min_length, self.__target_area / self.__min_length)
            height = self.__target_area / width
            if height >= self.__min_length:
                area = width * height
                # Check if area is within tolerance
                if abs(area - self.__target_area) <= self.__area_tolerance:
                    # Create closed rectangular polyline
                    self.site = rg.Polyline([
                        rg.Point3d(0, 0, 0),
                        rg.Point3d(width, 0, 0),
                        rg.Point3d(width, height, 0),
                        rg.Point3d(0, height, 0),
                        rg.Point3d(0, 0, 0)
                    ])
                    return self.site
        # Return None if no valid site found
        return None

    def __random_rectangle_in_site(self, z=0.0, max_attempts=1000):
        """
        Generates a random rectangle (with jittered corners) inside the site boundary at elevation z.
        Returns either a Polyline or a periodic interpolated Curve.
        """
        # Offset the site curve inward to define a safe region for the rectangle
        site_crv = rg.PolylineCurve(self.site).Offset(
            rg.Plane.WorldXY, -self.__site_margin, 0.01, rg.CurveOffsetCornerStyle.Sharp
        )[0]
        bbox = site_crv.GetBoundingBox(True)

        for _ in range(max_attempts):
            # Randomly choose rectangle size within bounding box limits
            max_width = bbox.Max.X - bbox.Min.X
            max_height = bbox.Max.Y - bbox.Min.Y
            width = random.uniform(self.__min_length, max_width * 0.8)
            height = random.uniform(self.__min_length, max_height * 0.8)

            # Randomly choose lower-left corner
            x = random.uniform(bbox.Min.X, bbox.Max.X - width)
            y = random.uniform(bbox.Min.Y, bbox.Max.Y - height)

            # Define rectangle corner points
            rect_pts = [
                rg.Point3d(x, y, z),
                rg.Point3d(x + width, y, z),
                rg.Point3d(x + width, y + height, z),
                rg.Point3d(x, y + height, z)
            ]

            # Apply jitter to each corner for irregularity
            jitter_range = 0.1 * min(width, height)
            jittered_pts = [
                rg.Point3d(pt.X + random.uniform(-jitter_range, jitter_range),
                           pt.Y + random.uniform(-jitter_range, jitter_range),
                           z)
                for pt in rect_pts
            ]
            jittered_pts.append(jittered_pts[0])  # Close the loop

            # Ensure all points are inside the offset site curve
            if all(site_crv.Contains(p, rg.Plane.WorldXY, 0.01) == rg.PointContainment.Inside for p in jittered_pts):
                # Randomly return either a Polyline or a periodic interpolated curve
                if random.random() < 0.5:
                    return rg.Polyline(jittered_pts)
                else:
                    curve = rg.Curve.CreateInterpolatedCurve(jittered_pts[:-1], 3)
                    return rg.Curve.CreatePeriodicCurve(curve)
        return None

    def generate_volume(self):
        """
        Generates the main building volume by lofting between a random base and roof curve
        (either polyline or spline), both contained within the site boundary.
        Sets self.__height and self.volume.
        Returns the resulting Brep or None if unsuccessful.
        """
        if not self.site:
            return None

        # Generate random base and roof curves (can be polyline or spline)
        base = self.__random_rectangle_in_site(z=0.0)
        self.__height = random.uniform(self.__min_height, self.__max_height)
        roof = self.__random_rectangle_in_site(z=self.__height)

        if not base or not roof:
            return None

        # Ensure both are curves (convert polylines if needed)
        base_crv = base if isinstance(base, rg.Curve) else rg.PolylineCurve(base)
        roof_crv = roof if isinstance(roof, rg.Curve) else rg.PolylineCurve(roof)

        # Loft between base and roof to create the main volume
        loft = rg.Brep.CreateFromLoft(
            [base_crv, roof_crv],
            rg.Point3d.Unset,
            rg.Point3d.Unset,
            rg.LoftType.Normal,
            False
        )

        if loft and len(loft) > 0:
            # Cap planar holes to make a solid if possible
            capped = loft[0].CapPlanarHoles(0.01)
            if capped and capped.IsSolid:
                self.volume = capped
            else:
                self.volume = loft[0]  # fallback to uncapped loft
            return self.volume

        return None

    def generate_storeys(self):
        """
        Splits the building volume into storeys by extruding the site curve at random heights,
        then intersecting each extruded box with the main volume.
        Returns a list of Breps, one per storey, and stores them in self.storeys.
        """
        if not self.site or not self.volume or not self.__height:
            return None

        # --- PARAMETERS: ceiling height range (in meters) ---
        min_ceiling = 2.8
        max_ceiling = 4.2

        # 1. Generate random level heights that sum to the total building height
        level_heights = []
        remaining = self.__height
        while remaining - min_ceiling > min_ceiling:
            h = random.uniform(min_ceiling, min(max_ceiling, remaining))
            level_heights.append(h)
            remaining -= h
        # Add the last level to use up the remaining height
        if remaining > 0.5:
            level_heights.append(remaining)

        # 2. For each level, extrude the site curve to create a box at the correct elevation
        site_crv = self.site if isinstance(self.site, rg.Curve) else rg.PolylineCurve(self.site)
        storeys = []
        elevation = 0.0

        for height in level_heights:
            # Move the site curve up to the current elevation
            moved_crv = site_crv.DuplicateCurve()
            moved_crv.Translate(rg.Vector3d(0, 0, elevation))

            # Try to create a planar Brep from the moved curve
            extrusion = moved_crv.ToNurbsCurve().Offset(rg.Plane.WorldXY, 0.0, 0.01, rg.CurveOffsetCornerStyle.Sharp)
            if extrusion and len(extrusion) > 0:
                brep = rg.Brep.CreatePlanarBreps(extrusion[0])
                if brep and len(brep) > 0:
                    # Create a box Brep for the storey using the site corners at base and top
                    cap = rg.Brep.CreateFromBox(
                        [rg.Point3d(p.X, p.Y, elevation) for p in self.site[:-1]] +
                        [rg.Point3d(p.X, p.Y, elevation + height) for p in self.site[:-1]]
                    )
                else:
                    cap = None
            else:
                # Fallback: extrude the curve to create the storey volume
                cap = rg.Extrusion.Create(moved_crv, height, True).ToBrep()

            # 3. Intersect the storey box with the main building volume to get the actual storey shape
            if cap:
                inter = rg.Brep.CreateBooleanDifference(cap, self.volume, 0.01)
                if inter and len(inter) > 0:
                    storeys.append(inter[0])
            elevation += height

        # Store and return the list of storey Breps
        self.storeys = storeys
        return storeys

    def generate_slabs(self):
        """
        Generates slabs for the building:
        - Ground floor slab at the base of the first storey
        - Intermediate slabs at the base of each upper storey
        - Roof slab at the top of the building volume
        Returns a list: [floor_slab, ...intermediate_slabs..., roof_slab]
        """
        if not hasattr(self, "storeys") or not self.storeys:
            return None

        self.slabs = []

        # --- Ground floor slab: use the lowest face of the first storey ---
        base_faces = self.storeys[0].Faces
        base_face = min(
            base_faces,
            key=lambda f: 0.5 * (f.GetBoundingBox(True).Max.Z - f.GetBoundingBox(True).Min.Z)
        )
        base_edge = base_face.OuterLoop.To3dCurve()
        base_extr = rg.Extrusion.Create(base_edge, -self.__slab_thickness, True)
        self.floor_slab = base_extr.ToBrep() if base_extr else None

        # --- Intermediate slabs: use the lowest face of each upper storey ---
        for storey in self.storeys[1:]:
            faces = storey.Faces
            bottom_face = min(
                faces,
                key=lambda f: 0.5 * (f.GetBoundingBox(True).Max.Z - f.GetBoundingBox(True).Min.Z)
            )
            bottom_crv = bottom_face.OuterLoop.To3dCurve()
            slab_extr = rg.Extrusion.Create(bottom_crv, -self.__slab_thickness, True)
            if slab_extr:
                self.slabs.append(slab_extr.ToBrep())

        # --- Roof slab: use the top face of the main building volume ---
        top_face = sorted(self.volume.Faces, key=lambda f: 0.5*(f.GetBoundingBox(True).Max.Z - f.GetBoundingBox(True).Min.Z))[0]
        roof_crv = top_face.OuterLoop.To3dCurve()
        roof_extr = rg.Extrusion.Create(roof_crv, -self.__slab_thickness, True)
        self.roof_slab = roof_extr.ToBrep() if roof_extr else None

        return [self.floor_slab] + self.slabs + [self.roof_slab]

    def __random_tilted_vector(self):
        """
        Generates a random 3D vector tilted from the vertical (Z axis) by up to the maximum allowed wall tilt.
        The tilt is applied in the XZ plane (Y=0).
        Returns:
            Rhino.Geometry.Vector3d: The resulting unit vector.
        """
        # Random tilt angle in degrees within allowed range
        angle_deg = random.uniform(-self.__max_wall_tilt_deg, self.__max_wall_tilt_deg)
        angle_rad = math.radians(angle_deg)
        # X component is the sine of the tilt angle, Z is the cosine (always positive for upward direction)
        x = math.sin(angle_rad)
        z = abs(math.cos(angle_rad))
        return rg.Vector3d(x, 0, z)

    def __make_wall_profile(self, curve, thickness):
        """
        Creates a closed wall profile curve by offsetting the input curve and connecting the ends.
        Args:
            curve (rg.Curve): The centerline curve of the wall.
            thickness (float): Wall thickness (offset distance).
        Returns:
            rg.Curve or None: Closed profile curve, or None if failed.
        """
        # Offset the curve inward (negative thickness)
        offsets = curve.Offset(rg.Plane.WorldXY, -thickness, 0.01, rg.CurveOffsetCornerStyle.Sharp)
        if not offsets or len(offsets) == 0:
            return None
        offset_crv = offsets[0]

        # Get start/end points of original and offset curves
        p_start_orig = curve.PointAtStart
        p_start_off = offset_crv.PointAtStart
        p_end_orig = curve.PointAtEnd
        p_end_off = offset_crv.PointAtEnd

        # Create lines to cap the ends between original and offset
        cap_start = rg.Line(p_start_orig, p_start_off).ToNurbsCurve()
        cap_end = rg.Line(p_end_orig, p_end_off).ToNurbsCurve()

        # Join all segments into a closed profile
        joined = rg.Curve.JoinCurves([curve, cap_end, offset_crv, cap_start])
        if joined and len(joined) > 0 and joined[0].IsClosed:
            return joined[0]
        return None


    def to_gh_tree(self, nested_list):
        """
        Converts a nested Python list (list of lists) into a Grasshopper DataTree.
        Each sublist becomes a branch in the DataTree.

        Args:
            nested_list (list of lists): The nested list to convert.

        Returns:
            Grasshopper.DataTree[object]: The resulting DataTree.
        """
        tree = DataTree[object]()
        for i, sublist in enumerate(nested_list):
            path = GH_Path(i)  # Each sublist gets its own branch path
            for item in sublist:
                tree.Add(item, path)
        return tree

    def generate_walls(self):
        """
        For each storey, generates 1–2 random wall Breps as extruded closed profiles (from random lines).
        Returns a Grasshopper DataTree of wall Breps.
        """
        if not hasattr(self, "storeys") or not self.storeys:
            return None

        self.walls = []

        def get_valid_wall_line(base_crv, z, inset=1.25, max_attempts=100):
            """
            Generates a random line (as a NurbsCurve) between two points inside an inset offset of the base curve.
            """
            offset_crvs = base_crv.Offset(rg.Plane.WorldXY, inset, 0.01, rg.CurveOffsetCornerStyle.Sharp)
            if not offset_crvs or len(offset_crvs) == 0:
                return None
            offset_crv = offset_crvs[0]
            bbox = offset_crv.GetBoundingBox(True)

            def random_point_in_crv():
                for _ in range(max_attempts):
                    x = random.uniform(bbox.Min.X, bbox.Max.X)
                    y = random.uniform(bbox.Min.Y, bbox.Max.Y)
                    pt = rg.Point3d(x, y, z)
                    if offset_crv.Contains(pt, rg.Plane.WorldXY, 0.01) == rg.PointContainment.Inside:
                        return pt
                return None

            pt1 = random_point_in_crv()
            pt2 = random_point_in_crv()
            if pt1 and pt2:
                return rg.Polyline([pt1, pt2]).ToNurbsCurve()
            return None

        for i, storey in enumerate(self.storeys):
            # Use the lowest face (by height) as the base for wall generation
            base_face = sorted(
                storey.Faces,
                key=lambda f: 0.5 * (f.GetBoundingBox(True).Max.Z - f.GetBoundingBox(True).Min.Z)
            )[0]
            base_crv = base_face.OuterLoop.To3dCurve()
            base_brep = rg.Brep.CreatePlanarBreps(base_crv)
            if not base_brep or len(base_brep) == 0:
                self.walls.append([])
                continue

            base = base_brep[0]
            base_bbox = base.GetBoundingBox(True)
            walls_this_storey = []

            num_lines = random.randint(1, 2)
            for _ in range(num_lines):
                # Generate a random wall line inside the storey base
                curve = get_valid_wall_line(base_crv, base_bbox.Min.Z)
                if not curve:
                    continue

                # Create a closed wall profile by offsetting the curve
                thickness = random.uniform(self.__min_wall_thickness, self.__max_wall_thickness)
                curve_offset = self.__make_wall_profile(curve, thickness)
                if not curve_offset:
                    continue

                # Determine extrusion height (up to next storey or roof)
                try:
                    top_z = self.storeys[i + 1].GetBoundingBox(True).Min.Z
                except IndexError:
                    top_z = self.__height

                base_z = base_bbox.Min.Z
                height = top_z - base_z

                # Apply a random tilt to the wall extrusion vector
                vector = self.__random_tilted_vector()
                vector.Unitize()
                vector *= (height - self.__slab_thickness)

                # Move wall profile up by slab thickness to avoid overlap
                curve_offset.Translate(self.__slab_thickness * rg.Vector3d.ZAxis)

                # Extrude the wall profile along the tilted vector
                extrusion = rg.Extrusion.Create(curve_offset, vector.Length, True)
                if extrusion:
                    walls_this_storey.append(extrusion.ToBrep())

            self.walls.append(walls_this_storey)

        return self.to_gh_tree(self.walls)

    def generate_columns(self):
        """
        For each storey, creates 1–3 columns as extruded profile curves (rectangle or spline, periodic).
        Returns a Grasshopper DataTree of column Breps.
        """
        if not hasattr(self, "storeys") or not self.storeys:
            return None

        self.columns = []

        def get_valid_column_point(base_crv, z, inset=1.25, max_attempts=100):
            """
            Finds a random point inside an inset offset of the base curve at elevation z.
            """
            offset_crvs = base_crv.Offset(rg.Plane.WorldXY, inset, 0.01, rg.CurveOffsetCornerStyle.Sharp)
            if not offset_crvs or len(offset_crvs) == 0:
                return None
            offset_crv = offset_crvs[0]
            bbox = offset_crv.GetBoundingBox(True)
            for _ in range(max_attempts):
                x = random.uniform(bbox.Min.X, bbox.Max.X)
                y = random.uniform(bbox.Min.Y, bbox.Max.Y)
                pt = rg.Point3d(x, y, z)
                if offset_crv.Contains(pt, rg.Plane.WorldXY, 0.01) == rg.PointContainment.Inside:
                    return pt
            return None

        for i, storey in enumerate(self.storeys):
            # Use the lowest face as the base for column generation
            base_face = sorted(
                storey.Faces,
                key=lambda f: 0.5 * (f.GetBoundingBox(True).Max.Z - f.GetBoundingBox(True).Min.Z)
            )[0]
            base_crv = base_face.OuterLoop.To3dCurve()
            base_brep = rg.Brep.CreatePlanarBreps(base_crv)
            if not base_brep or len(base_brep) == 0:
                self.columns.append([])
                continue

            base = base_brep[0]
            base_bbox = base.GetBoundingBox(True)
            columns_this_storey = []

            num_columns = random.randint(1, 3)
            for _ in range(num_columns):
                pt = get_valid_column_point(base_crv, base_bbox.Min.Z)
                if not pt:
                    continue

                # Create column profile at the point: rectangle or periodic spline
                size_x = random.uniform(0.3, 0.7)
                size_y = random.uniform(0.3, 0.7)
                plane = rg.Plane(pt, rg.Vector3d.ZAxis)
                rect_crv = rg.Rectangle3d(plane, size_x, size_y).ToNurbsCurve()
                if random.random() < 0.5:
                    # Use periodic spline profile
                    corners = [
                        plane.PointAt(size_x / 2, size_y / 2),
                        plane.PointAt(-size_x / 2, size_y / 2),
                        plane.PointAt(-size_x / 2, -size_y / 2),
                        plane.PointAt(size_x / 2, -size_y / 2),
                        plane.PointAt(size_x / 2, size_y / 2)
                    ]
                    spline = rg.Curve.CreateInterpolatedCurve(corners, 3)
                    profile = rg.Curve.CreatePeriodicCurve(spline)
                else:
                    # Use rectangle profile
                    profile = rect_crv

                # Determine extrusion height (up to next storey or roof)
                try:
                    top_z = self.storeys[i + 1].GetBoundingBox(True).Min.Z
                except IndexError:
                    top_z = self.__height

                base_z = pt.Z
                height = top_z - base_z
                if height <= 0.01:
                    continue

                # Apply random tilt and move profile up by slab thickness
                vector = self.__random_tilted_vector()
                vector.Unitize()
                vector *= (height - self.__slab_thickness)
                profile.Translate(self.__slab_thickness * rg.Vector3d.ZAxis)

                # Extrude the profile along the tilted vector
                extrusion = rg.Extrusion.Create(profile, vector.Length, True)
                if extrusion:
                    columns_this_storey.append(extrusion.ToBrep())

            self.columns.append(columns_this_storey)

        return self.to_gh_tree(self.columns)

if run:
    # Instantiate and generate site
    bldg = Building()
    site = bldg.generate_site()
    volume = bldg.generate_volume()
    storeys = bldg.generate_storeys()
    slabs = bldg.generate_slabs()
    walls = bldg.generate_walls()
    columns = bldg.generate_columns()

    # Building object
    building = bldg
