Shader "SakurabashiDoori/2D/Multiply Lighting Mask"
{
    Properties
    {
        [PerRendererData] _MainTex ("Mask Texture", 2D) = "white" {}
        _Color ("Mask Tint", Color) = (1, 1, 1, 1)
        _Strength ("Strength", Range(0, 1)) = 1
        _Brightness ("Mask Brightness", Range(0, 2)) = 1
        _MinMultiplier ("Minimum Multiplier", Range(0, 1)) = 0

        [HideInInspector] _StencilComp ("Stencil Comparison", Float) = 8
        [HideInInspector] _Stencil ("Stencil ID", Float) = 0
        [HideInInspector] _StencilOp ("Stencil Operation", Float) = 0
        [HideInInspector] _StencilWriteMask ("Stencil Write Mask", Float) = 255
        [HideInInspector] _StencilReadMask ("Stencil Read Mask", Float) = 255
        [HideInInspector] _ColorMask ("Color Mask", Float) = 15
        [HideInInspector] _UseUIAlphaClip ("Use Alpha Clip", Float) = 0
    }

    SubShader
    {
        Tags
        {
            "Queue" = "Transparent+10"
            "IgnoreProjector" = "True"
            "RenderType" = "Transparent"
            "PreviewType" = "Plane"
            "CanUseSpriteAtlas" = "True"
        }

        Stencil
        {
            Ref [_Stencil]
            Comp [_StencilComp]
            Pass [_StencilOp]
            ReadMask [_StencilReadMask]
            WriteMask [_StencilWriteMask]
        }

        Cull Off
        Lighting Off
        ZWrite Off
        ZTest LEqual
        ColorMask [_ColorMask]
        Blend DstColor Zero

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 2.0
            #pragma multi_compile_instancing
            #pragma multi_compile __ UNITY_UI_CLIP_RECT
            #pragma multi_compile __ UNITY_UI_ALPHACLIP

            #include "UnityCG.cginc"
            #include "UnityUI.cginc"

            struct appdata_t
            {
                float4 vertex : POSITION;
                fixed4 color : COLOR;
                float2 texcoord : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
                fixed4 color : COLOR;
                float2 texcoord : TEXCOORD0;
                float4 worldPosition : TEXCOORD1;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            sampler2D _MainTex;
            float4 _MainTex_ST;
            fixed4 _Color;
            fixed _Strength;
            fixed _Brightness;
            fixed _MinMultiplier;
            float4 _ClipRect;

            v2f vert(appdata_t input)
            {
                v2f output;
                UNITY_SETUP_INSTANCE_ID(input);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(output);

                output.worldPosition = input.vertex;
                output.vertex = UnityObjectToClipPos(output.worldPosition);
                output.texcoord = TRANSFORM_TEX(input.texcoord, _MainTex);
                output.color = input.color * _Color;
                return output;
            }

            fixed4 frag(v2f input) : SV_Target
            {
                fixed4 mask = tex2D(_MainTex, input.texcoord) * input.color;
                fixed effect = saturate(mask.a * _Strength);
                fixed3 darkenColor = max(saturate(mask.rgb * _Brightness), _MinMultiplier.xxx);
                fixed3 multiplier = lerp(fixed3(1, 1, 1), darkenColor, effect);

                #ifdef UNITY_UI_CLIP_RECT
                fixed clipFactor = UnityGet2DClipping(input.worldPosition.xy, _ClipRect);
                multiplier = lerp(fixed3(1, 1, 1), multiplier, clipFactor);
                #endif

                #ifdef UNITY_UI_ALPHACLIP
                clip(effect - 0.001);
                #endif

                return fixed4(multiplier, 1);
            }
            ENDCG
        }
    }

    Fallback Off
}
