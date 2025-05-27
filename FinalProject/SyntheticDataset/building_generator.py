"""Building Generator"""

import Rhino.Geometry as rg
import Grasshopper
from Grasshopper import DataTree
from Grasshopper.Kernel.Data import GH_Path
import random
import math

class Building:
    def __init__(self):
        self.__target_area = 300.0
        self.__min_length = 12.0
        self.__area_tolerance = 1.0

        self.__min_height = 8.0   # Minimum building height
        self.__max_height = 20.0  # Maximum building height
        self.__height = None

        self.__min_slab_thickness = 0.15  # meters
        self.__max_slab_thickness = 0.35
        self.__slab_thickness = random.uniform(self.__min_slab_thickness, self.__max_slab_thickness)

        self.floor_slab = None
        self.slabs = []
        self.roof_slab = None

        self.__min_wall_thickness = 0.15
        self.__max_wall_thickness = 0.35
        self.__max_wall_tilt_deg = 5.0

        self.walls = []  # List of lists of wall breps, one sublist per storey

        self.site = None
        self.__site_margin = 3.0
        self.volume = None

    def generate_site(self, max_attempts=100):
        for _ in range(max_attempts):
            width = random.uniform(self.__min_length, self.__target_area / self.__min_length)
            height = self.__target_area / width
            if height >= self.__min_length:
                area = width * height
                if abs(area - self.__target_area) <= self.__area_tolerance:
                    self.site = rg.Polyline([
                        rg.Point3d(0, 0, 0),
                        rg.Point3d(width, 0, 0),
                        rg.Point3d(width, height, 0),
                        rg.Point3d(0, height, 0),
                        rg.Point3d(0, 0, 0)
                    ])
                    return self.site
        return None

    def __random_rectangle_in_site(self, z=0.0, max_attempts=1000):
        # Offset inward in the XY plane (negative distance)
        site_crv = rg.PolylineCurve(self.site).Offset(rg.Plane.WorldXY, -self.__site_margin, 0.01, rg.CurveOffsetCornerStyle.Sharp)[0]

        bbox = site_crv.GetBoundingBox(True)

        for _ in range(max_attempts):
            max_width = bbox.Max.X - bbox.Min.X
            max_height = bbox.Max.Y - bbox.Min.Y
            width = random.uniform(self.__min_length, max_width * 0.8)
            height = random.uniform(self.__min_length, max_height * 0.8)

            x = random.uniform(bbox.Min.X, bbox.Max.X - width)
            y = random.uniform(bbox.Min.Y, bbox.Max.Y - height)

            # Base rectangle points
            pt0 = rg.Point3d(x, y, z)
            pt1 = rg.Point3d(x + width, y, z)
            pt2 = rg.Point3d(x + width, y + height, z)
            pt3 = rg.Point3d(x, y + height, z)

            rect_pts = [pt0, pt1, pt2, pt3]

            # Apply jitter
            jitter_range = 0.1 * min(width, height)
            jittered_pts = []
            for pt in rect_pts:
                dx = random.uniform(-jitter_range, jitter_range)
                dy = random.uniform(-jitter_range, jitter_range)
                jittered_pts.append(rg.Point3d(pt.X + dx, pt.Y + dy, z))
            jittered_pts.append(jittered_pts[0])  # Close loop

            # Check if all points lie inside site
            if all(site_crv.Contains(p, rg.Plane.WorldXY, 0.01) == rg.PointContainment.Inside for p in jittered_pts):
                # Randomly choose to create a PolylineCurve or InterpolatedCurve
                if random.random() < 0.5:
                    return rg.Polyline(jittered_pts)  # Polygon
                else:
                    curve = rg.Curve.CreateInterpolatedCurve(jittered_pts[:-1], 3)
                    curve = rg.Curve.CreatePeriodicCurve(curve)  
                    return curve
        return None

    def generate_volume(self):
        if not self.site:
            return None

        # Generate base and roof curves (randomly polyline or spline)
        base = self.__random_rectangle_in_site(z=0.0)
        self.__height = random.uniform(self.__min_height, self.__max_height)
        roof = self.__random_rectangle_in_site(z=self.__height)

        if not base or not roof:
            return None

        # Convert to curve if they are polylines
        base_crv = base if isinstance(base, rg.Curve) else rg.PolylineCurve(base)
        roof_crv = roof if isinstance(roof, rg.Curve) else rg.PolylineCurve(roof)

        # Loft between base and roof
        loft = rg.Brep.CreateFromLoft([base_crv, roof_crv], rg.Point3d.Unset, rg.Point3d.Unset, rg.LoftType.Normal, False)

        if loft and len(loft) > 0:
            capped = loft[0].CapPlanarHoles(0.01)
            if capped and capped.IsSolid:
                self.volume = capped
            else:
                self.volume = loft[0]  # fallback to uncapped
            return self.volume

        return None

    def generate_storeys(self):
        if not self.site or not self.volume or not self.__height:
            return None

        # PARAMETERS: ceiling height range (in meters)
        min_ceiling = 2.8
        max_ceiling = 4.2

        # 1. Generate random level heights
        level_heights = []
        remaining = self.__height
        while remaining - min_ceiling > min_ceiling:
            h = random.uniform(min_ceiling, min(max_ceiling, remaining))
            level_heights.append(h)
            remaining -= h

        # Fix last level to use up exact height
        if remaining > 0.5:
            level_heights.append(remaining)

        # 2. Generate level boxes from base polygon
        site_crv = self.site if isinstance(self.site, rg.Curve) else rg.PolylineCurve(self.site)
        storeys = []
        elevation = 0.0

        for height in level_heights:
            # Extrude base curve from current elevation to elevation + height
            vector = rg.Vector3d(0, 0, height)
            base_plane = rg.Plane(rg.Point3d(0, 0, elevation), rg.Vector3d.ZAxis)
            moved_crv = site_crv.DuplicateCurve()
            moved_crv.Translate(rg.Vector3d(0, 0, elevation))

            extrusion = moved_crv.ToNurbsCurve().Offset(rg.Plane.WorldXY, 0.0, 0.01, rg.CurveOffsetCornerStyle.Sharp)
            if extrusion and len(extrusion) > 0:
                brep = rg.Brep.CreatePlanarBreps(extrusion[0])
                if brep and len(brep) > 0:
                    cap = rg.Brep.CreateFromBox([
                        rg.Point3d(p.X, p.Y, elevation) for p in self.site[:-1]
                    ] + [rg.Point3d(p.X, p.Y, elevation + height) for p in self.site[:-1]])
                else:
                    cap = None
            else:
                cap = rg.Extrusion.Create(moved_crv, height, True).ToBrep()

            # 3. Boolean intersection between level box and volume
            if cap:
                inter = rg.Brep.CreateBooleanDifference(cap, self.volume, 0.01)
                if inter and len(inter) > 0:
                    storeys.append(inter[0])
            elevation += height

        # Store result
        self.storeys = storeys
        return storeys

    def generate_slabs(self):
        if not hasattr(self, "storeys") or not self.storeys:
            return None

        self.slabs = []

        # STEP 1: Ground floor slab from lower boundary of first storey
        base_faces = self.storeys[0].Faces
        base_face = sorted(base_faces, key=lambda f: 0.5*(f.GetBoundingBox(True).Max.Z - f.GetBoundingBox(True).Min.Z))[0]
        base_edge = base_face.OuterLoop.To3dCurve()

        base_extr = rg.Extrusion.Create(base_edge, -self.__slab_thickness, True)
        self.floor_slab = base_extr.ToBrep() if base_extr else None

        # STEP 2: Intermediate slabs from bottoms of upper storeys
        for storey in self.storeys[1:]:
            faces = storey.Faces
            bottom_face = sorted(faces, key=lambda f: 0.5*(f.GetBoundingBox(True).Max.Z - f.GetBoundingBox(True).Min.Z))[0]
            bottom_crv = bottom_face.OuterLoop.To3dCurve()

            slab = rg.Extrusion.Create(bottom_crv, -self.__slab_thickness, True)
            if slab:
                self.slabs.append(slab.ToBrep())

        # STEP 3: Roof slab from top face of volume
        top_face = sorted(self.volume.Faces, key=lambda f: 0.5*(f.GetBoundingBox(True).Max.Z - f.GetBoundingBox(True).Min.Z))[0]
        roof_crv = top_face.OuterLoop.To3dCurve()
        roof_extr = rg.Extrusion.Create(roof_crv, -self.__slab_thickness, True)
        self.roof_slab = roof_extr.ToBrep() if roof_extr else None

        return [self.floor_slab] + self.slabs + [self.roof_slab]

    def __random_tilted_vector(self):
        angle_deg = random.uniform(-self.__max_wall_tilt_deg, self.__max_wall_tilt_deg)
        angle_rad = math.radians(angle_deg)
        x = math.sin(angle_rad)
        z = abs(math.cos(angle_rad))
        return rg.Vector3d(x, 0, z)

    def __make_wall_profile(self, curve, thickness):
        # Offset inward (or outward, you can swap sign here if needed)
        offsets = curve.Offset(rg.Plane.WorldXY, -thickness, 0.01, rg.CurveOffsetCornerStyle.Sharp)
        if not offsets or len(offsets) == 0:
            return None
        offset_crv = offsets[0]

        # Connect start/end points between original and offset
        p1a = curve.PointAtStart
        p1b = offset_crv.PointAtStart
        p2a = curve.PointAtEnd
        p2b = offset_crv.PointAtEnd

        cap1 = rg.Line(p1a, p1b).ToNurbsCurve()
        cap2 = rg.Line(p2a, p2b).ToNurbsCurve()

        joined = rg.Curve.JoinCurves([curve, cap2, offset_crv, cap1])
        if joined and len(joined) > 0 and joined[0].IsClosed:
            return joined[0]
        return None


    def to_gh_tree(self, nested_list):
        tree = DataTree[object]()
        for i, sublist in enumerate(nested_list):
            path = GH_Path(i)
            for item in sublist:
                tree.Add(item, path)
        return tree

    def generate_walls(self):
        if not hasattr(self, "storeys") or not self.storeys:
            return None

        self.walls = []

        def get_valid_wall_line(base_crv, z, inset=1.25, max_attempts=100):
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
            base_face = sorted(storey.Faces, key=lambda f: 0.5 * (f.GetBoundingBox(True).Max.Z - f.GetBoundingBox(True).Min.Z))[0]
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
                curve = get_valid_wall_line(base_crv, base_bbox.Min.Z)
                if not curve:
                    continue

                # Offset to closed wall profile
                thickness = random.uniform(self.__min_wall_thickness, self.__max_wall_thickness)
                curve_offset = self.__make_wall_profile(curve, thickness)
                if not curve_offset:
                    continue

                # Determine height up to next storey or roof
                try:
                    top_z = self.storeys[i + 1].GetBoundingBox(True).Min.Z
                except IndexError:
                    top_z = self.__height

                base_z = base_bbox.Min.Z
                height = top_z - base_z

                vector = self.__random_tilted_vector()
                vector.Unitize()
                vector *= (height - self.__slab_thickness)

                curve_offset.Translate(self.__slab_thickness * rg.Vector3d.ZAxis)

                extrusion = rg.Extrusion.Create(curve_offset, vector.Length, True)
                if extrusion:
                    walls_this_storey.append(extrusion.ToBrep())

            self.walls.append(walls_this_storey)

        return self.to_gh_tree(self.walls)


# Instantiate and generate site
bldg = Building()
site = bldg.generate_site()
volume = bldg.generate_volume()
storeys = bldg.generate_storeys()
slabs = bldg.generate_slabs()
walls = bldg.generate_walls()
