module Leaflet exposing (LeafletMap)

import Browser
import Html exposing (Html, node)
import Html.Attributes exposing (attribute)


type LeafletMap
    = LeafletMap
        { id : String
        , routes : List Route
        , tileUrl : String
        , markers : List Marker
        }



-- TODO make it opaque


type alias Route =
    String



-- TODO make it opaque


type alias Marker =
    { latitude : String
    , longitude : String
    , body : Html Never
    }


type alias Flags =
    { routes : List Route
    , tileUrl : String
    }


view : LeafletMap -> Html Never
view (LeafletMap leafletMap) =
    let
        markers =
            List.map viewMarker leafletMap.markers

        routes =
            List.map viewRoute leafletMap.routes
    in
    node "leaflet-map"
        [ attribute "tile-url" leafletMap.tileUrl
        , attribute "map-id" leafletMap.id
        ]
        (markers ++ routes)


viewMarker : Marker -> Html Never
viewMarker marker =
    node "marker"
        [ attribute "lon" marker.longitude
        , attribute "lat" marker.latitude
        ]
        [ marker.body ]


viewRoute : Route -> Html Never
viewRoute route =
    node "leaflet-route" [ attribute "geojson" route ] []


init : { mapId : String, tileUrl : String } -> LeafletMap
init { mapId, tileUrl } =
    LeafletMap { id = mapId, routes = [], tileUrl = tileUrl, markers = [] }


withRoutes : List Route -> LeafletMap -> LeafletMap
withRoutes routes (LeafletMap leafletMap) =
    LeafletMap { leafletMap | routes = routes }


withMarkers : List Marker -> LeafletMap -> LeafletMap
withMarkers markers (LeafletMap leafletMap) =
    LeafletMap { leafletMap | markers = markers }


main =
    let
        mainInit : Flags -> ( LeafletMap, Cmd Never )
        mainInit flags =
            ( init { mapId = "mapid", tileUrl = flags.tileUrl } |> withRoutes flags.routes, Cmd.none )
    in
    Browser.element
        { init = mainInit
        , update = \_ model -> ( model, Cmd.none )
        , subscriptions = \_ -> Sub.none
        , view = view
        }
